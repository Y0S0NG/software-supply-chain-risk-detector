"""
Drop structural features from the GNN graph dataset.

Each graph's node feature matrix data.x has shape (N, 27):
  columns  0–19 : package metadata features
  columns 20–26 : structural features (in_degree, out_degree, depth_from_root,
                  is_leaf, is_shared, graph_node_count, graph_edge_count)

This script keeps only columns [:20] and saves the result to a new cache file.
"""

import pickle
import sys
import os

sys.path.insert(0, os.path.abspath('..'))


INPUT_PATH  = '../data/gnn_graph_dataset.pkl'
OUTPUT_PATH = '../data/gnn_graph_metadata_only_dataset.pkl'
KEEP_DIMS   = 20   # package metadata features only

print(f'Loading {INPUT_PATH} ...')
with open(INPUT_PATH, 'rb') as f:
    graph_dataset = pickle.load(f)

print(f'Loaded {len(graph_dataset)} graphs.')

processed = []
for item in graph_dataset:
    data = item['data']
    # Slice feature matrix: (N, 27) → (N, 20)
    new_data = data.clone()
    new_data.x = data.x[:, :KEEP_DIMS]
    processed.append({
        'data'  : new_data,
        'label' : item['label'],
        'pkg_id': item['pkg_id'],
    })

print(f'Feature dim reduced: {graph_dataset[0]["data"].x.shape[1]} → {processed[0]["data"].x.shape[1]}')

print(f'Saving to {OUTPUT_PATH} ...')
with open(OUTPUT_PATH, 'wb') as f:
    pickle.dump(processed, f)

print(f'Done. Saved {len(processed)} graphs.')
