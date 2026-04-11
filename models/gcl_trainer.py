"""
Graph Contrastive Learning (GCL) trainer.

Implements:
  - Composed graph augmentations with controlled strength:
      edge_dropout, feature_masking, feature_noise, subgraph_sampling
  - Two structurally distinct but complementary augmentation views:
      view1 = edge_dropout + feature_masking
      view2 = subgraph_sampling + feature_noise
  - InfoNCE (NT-Xent) contrastive loss
  - GCLTrainer: wraps the GCLModel and drives the training loop
"""

from __future__ import annotations

import random
from typing import List, Tuple

import torch
import torch.nn.functional as F
from torch_geometric.data import Data


# ── Augmentation functions ──────────────────────────────────────────────────

def aug_edge_dropout(data: Data, drop_rate: float = 0.2) -> Data:
    """Randomly remove edges with probability `drop_rate`."""
    ei = data.edge_index
    if ei.shape[1] == 0:
        return data
    mask = torch.rand(ei.shape[1]) > drop_rate
    return Data(x=data.x, edge_index=ei[:, mask])


def aug_feature_masking(data: Data, mask_rate: float = 0.2) -> Data:
    """Zero-out each feature entry independently with probability `mask_rate`."""
    mask = (torch.rand_like(data.x) > mask_rate).float()
    return Data(x=data.x * mask, edge_index=data.edge_index)


def aug_feature_noise(data: Data, noise_std: float = 0.05) -> Data:
    """Add small zero-mean Gaussian noise to all node features."""
    noisy_x = data.x + torch.randn_like(data.x) * noise_std
    return Data(x=noisy_x, edge_index=data.edge_index)


def aug_subgraph(data: Data, keep_ratio: float = 0.8) -> Data:
    """
    Randomly sample a subgraph by keeping each node with probability `keep_ratio`.
    The root (index 0) is always preserved.
    """
    num_nodes = data.x.shape[0]
    if num_nodes <= 1:
        return data

    keep = torch.rand(num_nodes) < keep_ratio
    keep[0] = True  # always keep root

    keep_idx = keep.nonzero(as_tuple=True)[0]
    remap = torch.full((num_nodes,), -1, dtype=torch.long)
    remap[keep_idx] = torch.arange(len(keep_idx))

    ei = data.edge_index
    if ei.shape[1] > 0:
        mask = keep[ei[0]] & keep[ei[1]]
        new_ei = remap[ei[:, mask]]
    else:
        new_ei = ei

    return Data(x=data.x[keep_idx], edge_index=new_ei)


def augment_view1(data: Data) -> Data:
    """
    View 1: structural perturbation + feature masking.
    Stochastically applies edge dropout and/or feature masking.
    """
    if random.random() < 0.8:
        data = aug_edge_dropout(data, drop_rate=0.2)
    if random.random() < 0.8:
        data = aug_feature_masking(data, mask_rate=0.2)
    return data


def augment_view2(data: Data) -> Data:
    """
    View 2: topology sampling + feature noise.
    Stochastically applies subgraph sampling and/or feature noise.
    """
    if random.random() < 0.8:
        data = aug_subgraph(data, keep_ratio=0.8)
    if random.random() < 0.5:
        data = aug_feature_noise(data, noise_std=0.05)
    return data

# ── InfoNCE loss ─────────────────────────────────────────────────────────────

def info_nce_loss(
    z1: torch.Tensor,
    z2: torch.Tensor,
    temperature: float = 0.5,
) -> torch.Tensor:
    """
    NT-Xent / InfoNCE loss for a batch of graph pairs.

    Args:
        z1: (N, D) L2-normalized embeddings from augmented view 1
        z2: (N, D) L2-normalized embeddings from augmented view 2
        temperature: softmax temperature

    Returns:
        Scalar loss that encourages z1[i] ↔ z2[i] similarity and
        pushes apart embeddings from different graphs.
    """
    N = z1.shape[0]
    z = torch.cat([z1, z2], dim=0)                    # (2N, D)
    sim = torch.mm(z, z.t()) / temperature             # (2N, 2N)

    # Mask out self-similarity on the diagonal
    diag_mask = torch.eye(2 * N, dtype=torch.bool, device=z.device)
    sim = sim.masked_fill(diag_mask, float('-inf'))

    # Positive pair for row i (from view 1) is row N+i (view 2), and vice-versa
    pos_labels = torch.cat([
        torch.arange(N, 2 * N, device=z.device),
        torch.arange(0, N,     device=z.device),
    ])  # (2N,)

    return F.cross_entropy(sim, pos_labels)


# ── GCL Trainer ──────────────────────────────────────────────────────────────

class GCLTrainer:
    """
    Drives the Graph Contrastive Learning training loop.

    Usage::

        trainer = GCLTrainer(model, lr=1e-3, temperature=0.5, device='cpu')
        for epoch in range(num_epochs):
            loss = trainer.train_epoch(graph_batch)

        # After training, obtain encoder-only embeddings:
        emb = trainer.get_embedding(data, root_idx=0)
    """

    def __init__(
        self,
        model,
        lr: float = 1e-3,
        temperature: float = 0.5,
        device: str = 'cpu',
    ):
        self.model = model.to(device)
        self.device = device
        self.temperature = temperature
        self.optimizer = torch.optim.Adam(model.parameters(), lr=lr)

    def train_epoch(
        self, graph_batch: List[Tuple[Data, int]]
    ) -> float:
        """
        Run one gradient update over a batch of graphs.

        For each graph two independent random augmentations are created,
        both are forwarded through the shared GNN + projection head,
        and the InfoNCE loss is computed over all (positive, negative) pairs.

        Args:
            graph_batch: list of (Data, root_idx) — root_idx is always 0
                         after build_pyg_data.

        Returns:
            Loss value for this batch.
        """
        self.model.train()
        self.optimizer.zero_grad()

        z1_list: List[torch.Tensor] = []
        z2_list: List[torch.Tensor] = []

        for data, root_idx in graph_batch:
            # Skip degenerate graphs (empty or 1-D x tensors from cache)
            if data.x.dim() != 2 or data.x.shape[0] == 0:
                continue
            # Two structurally distinct augmented views of the same graph
            view1 = augment_view1(data).to(self.device)
            view2 = augment_view2(data).to(self.device)

            # Root is always at index 0 (guaranteed by build_pyg_data and aug_leaf_removal)
            z1 = self.model.forward_gcl(view1.x, view1.edge_index, root_idx=0)
            z2 = self.model.forward_gcl(view2.x, view2.edge_index, root_idx=0)

            z1_list.append(z1)
            z2_list.append(z2)

        if len(z1_list) < 2:
            return float('nan')  # batch shrank below InfoNCE minimum after filtering

        z1_batch = torch.stack(z1_list)  # (N, proj_out_dim)
        z2_batch = torch.stack(z2_list)

        loss = info_nce_loss(z1_batch, z2_batch, self.temperature)
        loss.backward()
        self.optimizer.step()

        return loss.item()

    @torch.no_grad()
    def get_embedding(self, data: Data, root_idx: int = 0) -> torch.Tensor:
        """
        Return the encoder-only root embedding (no projection head).

        Used after training to extract package representations for clustering.
        """
        self.model.eval()
        data = data.to(self.device)
        h = self.model.encode(data.x, data.edge_index)  # (N, embed_dim)
        return h[root_idx].cpu()
