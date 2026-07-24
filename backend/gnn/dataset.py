"""
MuleTrace — PyTorch Geometric Graph Dataset Converter
"""

import torch
import networkx as nx
from torch_geometric.data import Data
from backend.gnn.features import extract_account_features


def nx_to_pyg(G: nx.DiGraph):
    """Convert NetworkX DiGraph to PyTorch Geometric Data object."""
    X, y, account_nodes = extract_account_features(G)

    node_mapping = {acc: i for i, acc in enumerate(account_nodes)}
    edge_index_list = []

    for u, v, d in G.edges(data=True):
        if u in node_mapping and v in node_mapping:
            edge_index_list.append([node_mapping[u], node_mapping[v]])

    if not edge_index_list:
        edge_index = torch.zeros((2, 0), dtype=torch.long)
    else:
        edge_index = torch.tensor(edge_index_list, dtype=torch.long).t().contiguous()

    x_tensor = torch.tensor(X, dtype=torch.float)
    y_tensor = torch.tensor(y, dtype=torch.long)

    data = Data(x=x_tensor, edge_index=edge_index, y=y_tensor)

    # Train / Val masks (80/20 split)
    num_nodes = len(account_nodes)
    perm = torch.randperm(num_nodes)
    train_size = int(0.8 * num_nodes)

    train_mask = torch.zeros(num_nodes, dtype=torch.bool)
    val_mask = torch.zeros(num_nodes, dtype=torch.bool)

    train_mask[perm[:train_size]] = True
    val_mask[perm[train_size:]] = True

    data.train_mask = train_mask
    data.val_mask = val_mask

    return data, node_mapping, account_nodes
