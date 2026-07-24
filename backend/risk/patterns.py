"""
MuleTrace — Money Laundering Pattern Detector

Detects:
  1. Structuring / Smurfing (sub-$10,000 deposits to evade reporting)
  2. Rapid Cash-Out (incoming digital transfer followed by instant ATM withdrawal)
  3. Shared Device / IP Mule Ring Clusters
"""

import networkx as nx
from typing import List, Dict, Any


class PatternDetector:
    def __init__(self, G: nx.DiGraph):
        self.G = G

    def detect_structuring(self, min_amount: float = 9000.0, max_amount: float = 9995.0) -> List[Dict[str, Any]]:
        """Detect structuring / smurfing transfers under the regulatory threshold."""
        flagged_structuring = []
        for u, v, d in self.G.edges(data=True):
            if d.get("edge_type") == "TRANSFERRED_TO":
                amount = d.get("amount", 0.0)
                if min_amount <= amount <= max_amount:
                    flagged_structuring.append({
                        "source_account": u,
                        "target_account": v,
                        "amount": amount,
                        "channel": d.get("channel_type", "UPI"),
                        "timestamp": d.get("timestamp", ""),
                        "pattern": "STRUCTURING_SUB_10K",
                        "explanation": f"Sub-threshold transfer of ${amount:,.2f} evading $10,000 regulatory reporting line."
                    })
        return flagged_structuring

    def detect_rapid_cashout(self) -> List[Dict[str, Any]]:
        """Detect accounts receiving incoming transfers and instantly withdrawing at ATMs."""
        rapid_cashouts = []
        account_nodes = [n for n, d in self.G.nodes(data=True) if d.get("entity_type") == "Account"]

        for acc in account_nodes:
            # Check if has incoming UPI/WEB transfer AND outgoing ATM transfer
            in_edges = [d for _, _, d in self.G.in_edges(acc, data=True) if d.get("edge_type") == "TRANSFERRED_TO"]
            out_atm = [d for _, v, d in self.G.out_edges(acc, data=True) if d.get("channel_type") == "ATM" or v == "ATM-CASH-OUT"]

            if in_edges and out_atm:
                rapid_cashouts.append({
                    "account_id": acc,
                    "incoming_count": len(in_edges),
                    "atm_withdrawals": len(out_atm),
                    "pattern": "RAPID_CASHOUT_VELOCITY",
                    "explanation": f"Account received {len(in_edges)} incoming digital transfer(s) followed by immediate ATM cash-out."
                })
        return rapid_cashouts

    def detect_mule_clusters((self)) -> List[Dict[str, Any]]:
        """Detect clusters of accounts sharing Devices and IPs."""
        device_nodes = [n for n, d in self.G.nodes(data=True) if d.get("entity_type") == "Device" and self.G.degree(n) > 1]
        clusters = []

        for dev in device_nodes:
            connected_accs = list(self.G.predecessors(dev))
            if len(connected_accs) >= 2:
                clusters.append({
                    "device_id": dev,
                    "shared_account_count": len(connected_accs),
                    "member_accounts": connected_accs,
                    "pattern": "SHARED_DEVICE_MULE_RING",
                    "explanation": f"Device {dev} is shared across {len(connected_accs)} distinct customer accounts."
                })
        return clusters
