import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import SAGEConv


class GraphSAGEEncoder(nn.Module):
    """Two-layer GraphSAGE encoder matching the BFS depth of GraphGenerator."""

    def __init__(self, in_channels: int, hidden_channels: int, out_channels: int, num_layers: int = 2):
        super().__init__()
        self.num_layers = num_layers
        self.convs = nn.ModuleList()

        if num_layers == 1:
            self.convs.append(SAGEConv(in_channels, out_channels))
        else:
            self.convs.append(SAGEConv(in_channels, hidden_channels))
            for _ in range(num_layers - 2):
                self.convs.append(SAGEConv(hidden_channels, hidden_channels))
            self.convs.append(SAGEConv(hidden_channels, out_channels))

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        for i, conv in enumerate(self.convs):
            x = conv(x, edge_index)
            if i < self.num_layers - 1:
                x = F.relu(x)
        return x


class ProjectionHead(nn.Module):
    """Small MLP projection head used during GCL training only."""

    def __init__(self, in_dim: int, hidden_dim: int, out_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, out_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class GCLModel(nn.Module):
    """
    GraphSAGE encoder + projection head for Graph Contrastive Learning.

    During training, call forward_gcl() to get normalized projected embeddings.
    After training, call encode() to get raw encoder embeddings (no projection head).
    """

    def __init__(
        self,
        in_channels: int,
        hidden_channels: int,
        embed_dim: int,
        proj_hidden_dim: int = 64,
        proj_out_dim: int = 32,
        num_layers: int = 2,
    ):
        super().__init__()
        self.encoder = GraphSAGEEncoder(in_channels, hidden_channels, embed_dim, num_layers)
        self.projection_head = ProjectionHead(embed_dim, proj_hidden_dim, proj_out_dim)

    def encode(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """Return per-node embeddings from the encoder only."""
        return self.encoder(x, edge_index)

    def forward_gcl(
        self, x: torch.Tensor, edge_index: torch.Tensor, root_idx: int = 0
    ) -> torch.Tensor:
        """
        Full forward pass for GCL training.

        Returns the L2-normalized projected embedding of the root node.
        """
        h = self.encoder(x, edge_index)       # (N, embed_dim)
        h_root = h[root_idx]                  # (embed_dim,)
        z = self.projection_head(h_root)      # (proj_out_dim,)
        return F.normalize(z, dim=-1)
