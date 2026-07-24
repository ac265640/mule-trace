"""
MuleTrace — Feature Engineering for PyTorch Geometric GNN

Extracts 10+ topological, financial, and behavioral node features per account.
"""

import numpy as np
import networkx as nx
from typing import Dict, List, Tuple


def extract_account_features(G: nx.DiGraph) -> Tuple[np.ndarray, List[str], List[str]]:
    """Extract node feature matrix for all Account nodes in the graph."""
    account_nodes = [n for n, d in G.nodes(data=True) if d.get("entity_type") == "Account"]
    feature_list = []
    labels = []

    for acc in account_nodes:
        in_degree = G.in_degree(acc)
        out_degree = G.out_degree(acc)

        # Ingoing / Outgoing transfer amounts
        in_amounts = [d.get("amount", 0) for _, _, d in G.in_edges(acc, data=True) if d.get("edge_type") == "TRANSFERRED_TO"]
        out_amounts = [d.get("amount", 0) for _, _, d in G.out_edges(acc, data=True) if d.get("edge_type") == "TRANSFERRED_TO"]

        sum_in = float(sum(in_amounts))
        sum_out = float(sum(out_amounts))
        mean_in = float(np.mean(in_amounts)) if in_amounts else 0.0
        mean_out = float(np.mean(out_amounts)) if out_amounts else 0.0

        # Sub-$10k structuring count (<$10,000)
        structuring_count = sum(1 for amt in in_amounts + out_amounts if 9000 <= amt <= 9995)

        # Shared Devices & IPs count
        devices = [v for _, v, d in G.out_edges(acc, data=True) if d.get("edge_type") == "USED_DEVICE"]
        ips = [v for _, v, d in G.out_edges(acc, data=True) if d.get("edge_type") == "CONNECTED_IP"]

        shared_device_count = sum(1 for dev in devices if G.degree(dev) > 2)
        shared_ip_count = sum(1 for ip in ips if G.degree(ip) > 2)

        jur_risk = float(G.nodes[acc].get("jurisdiction_risk_weight", 0.2))
        is_mule = 1 if G.nodes[acc].get("is_mule", False) else 0

        feats = [
            in_degree,
            out_degree,
            sum_in / 10000.0,
            sum_out / 10000.0,
            mean_in / 10000.0,
            mean_out / 10000.0,
            structuring_count,
            shared_device_count,
            shared_ip_count,
            jur_risk,
        ]
        feature_list.append(feats)
        labels.append(is_mule)

    X = np.array(feature_list, dtype=np.float32)
    y = np.array(labels, dtype=np.int64)
    return X, y, account_nodes
