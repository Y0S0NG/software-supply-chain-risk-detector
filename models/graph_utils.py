from __future__ import annotations

from typing import Dict, List, Optional

import torch
from torch_geometric.data import Data


FEATURE_DIM = 27  # 20 package features + 7 structural features


def build_pyg_data(
    nodes_map: Dict,
    features_dict: Dict[str, List[float]],
    root_id: Optional[str] = None,
) -> tuple[Data, int]:
    """
    Convert a GraphGenerator nodes_map and per-node feature dict into a PyG Data object.

    The root node is placed at index 0 in the resulting tensor so that
    `h[0]` always refers to the seed package's embedding.

    Args:
        nodes_map:      dict[package_id -> PackageNode] from GraphGenerator.nodes_map
        features_dict:  dict[package_id -> list[float]] of full features per node
        root_id:        package_id of the seed/root node; moved to index 0 when given

    Returns:
        (data, root_idx) where root_idx is always 0
    """
    node_ids = list(nodes_map.keys())

    # Guarantee root is at position 0
    if root_id and root_id in node_ids:
        node_ids.remove(root_id)
        node_ids.insert(0, root_id)

    node_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    # Determine feature dimension from available data
    feat_dim = FEATURE_DIM
    for feat in features_dict.values():
        if feat:
            feat_dim = len(feat)
            break

    # Build node feature matrix
    x_rows: List[List[float]] = []
    for nid in node_ids:
        feat = features_dict.get(nid)
        x_rows.append(feat if feat else [0.0] * feat_dim)
    # Use explicit shape to avoid torch.tensor([]) producing a 1-D tensor
    if x_rows:
        x = torch.tensor(x_rows, dtype=torch.float)
    else:
        x = torch.zeros((0, feat_dim), dtype=torch.float)

    # Build edge index from depends_on relationships
    src_list: List[int] = []
    dst_list: List[int] = []
    for nid, node in nodes_map.items():
        src_idx = node_to_idx[nid]
        for dep_id in node.depends_on:
            if dep_id in node_to_idx:
                src_list.append(src_idx)
                dst_list.append(node_to_idx[dep_id])

    if src_list:
        edge_index = torch.tensor([src_list, dst_list], dtype=torch.long)
    else:
        edge_index = torch.zeros((2, 0), dtype=torch.long)

    return Data(x=x, edge_index=edge_index), 0
