"""
MuleTrace — Unified Entity Graph Builder (NetworkX)

Constructs heterogeneous multi-entity graphs connecting Accounts, Devices, IPs,
and Channels to detect cross-channel money mule networks.
"""

import os
import pandas as pd
import networkx as nx
from typing import Dict, Any

from backend.config import DATA_DIR


class GraphBuilder:
    def __init__(self):
        self.G = nx.DiGraph()

    def build(self, data: Dict[str, pd.DataFrame] = None) -> nx.DiGraph:
        if data is None:
            accounts_df = pd.read_csv(os.path.join(DATA_DIR, "accounts.csv"))
            transactions_df = pd.read_csv(os.path.join(DATA_DIR, "transactions.csv"))
            devices_df = pd.read_csv(os.path.join(DATA_DIR, "devices.csv"))
            ips_df = pd.read_csv(os.path.join(DATA_DIR, "ips.csv"))
        else:
            accounts_df = data["accounts"]
            transactions_df = data["transactions"]
            devices_df = data["devices"]
            ips_df = data["ips"]

        self.G.clear()

        # 1. Add Account Nodes
        for _, row in accounts_df.iterrows():
            self.G.add_node(
                row["account_id"],
                entity_type="Account",
                holder_name=row.get("holder_name", ""),
                jurisdiction=row.get("jurisdiction", "IN"),
                jurisdiction_risk_weight=float(row.get("jurisdiction_risk_weight", 0.2)),
                is_mule=bool(row.get("is_mule", False)),
            )

        # 2. Add Devices & Edges
        for _, row in devices_df.iterrows():
            dev_id = row["device_id"]
            acc_id = row["account_id"]
            if dev_id not in self.G:
                self.G.add_node(dev_id, entity_type="Device")
            self.G.add_edge(acc_id, dev_id, edge_type="USED_DEVICE")
            self.G.add_edge(dev_id, acc_id, edge_type="DEVICE_OF")

        # 3. Add IPs & Edges
        for _, row in ips_df.iterrows():
            ip_id = row["ip_address"]
            acc_id = row["account_id"]
            if ip_id not in self.G:
                self.G.add_node(ip_id, entity_type="IP")
            self.G.add_edge(acc_id, ip_id, edge_type="CONNECTED_IP")
            self.G.add_edge(ip_id, acc_id, edge_type="IP_OF")

        # 4. Add Transaction Edges (Transfers)
        for _, row in transactions_df.iterrows():
            src = row["source_account"]
            dst = row["target_account"]
            if src in self.G and dst in self.G:
                self.G.add_edge(
                    src, dst,
                    edge_type="TRANSFERRED_TO",
                    amount=float(row["amount"]),
                    channel_type=row.get("channel_type", "UPI"),
                    timestamp=row.get("timestamp", ""),
                    is_suspicious=bool(row.get("is_suspicious", False)),
                    pattern_type=row.get("pattern_type", "NORMAL"),
                )

        return self.G

    def get_stats(self) -> Dict[str, Any]:
        acc_nodes = [n for n, d in self.G.nodes(data=True) if d.get("entity_type") == "Account"]
        dev_nodes = [n for n, d in self.G.nodes(data=True) if d.get("entity_type") == "Device"]
        ip_nodes = [n for n, d in self.G.nodes(data=True) if d.get("entity_type") == "IP"]
        mule_accs = [n for n in acc_nodes if self.G.nodes[n].get("is_mule", False)]

        return {
            "total_nodes": self.G.number_of_nodes(),
            "total_edges": self.G.number_of_edges(),
            "account_nodes": len(acc_nodes),
            "device_nodes": len(dev_nodes),
            "ip_nodes": len(ip_nodes),
            "mule_accounts": len(mule_accs),
        }
