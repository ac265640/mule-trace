"""
MuleTrace — Gradient×Input Feature Attribution Explainer (XAI)
"""

import torch
from typing import Dict, Any, List

FEATURE_NAMES = [
    "In-Degree (Incoming Transfers)",
    "Out-Degree (Outgoing Transfers)",
    "Total Ingress Amount",
    "Total Egress Amount",
    "Average Incoming Amount",
    "Average Outgoing Amount",
    "Sub-$10k Structuring Count",
    "Shared Devices Count",
    "Shared IPs Count",
    "Jurisdiction Risk Weight",
]


class MuleExplainer:
    def __init__(self, model, data, account_ids: List[str], node_mapping: Dict[str, int]):
        self.model = model
        self.data = data
        self.account_ids = account_ids
        self.node_mapping = node_mapping

    def explain_account(self, account_id: str) -> Dict[str, Any]:
        """Compute Gradient × Input feature attributions for account."""
        if account_id not in self.node_mapping:
            return {"account_id": account_id, "error": "Account not found"}

        idx = self.node_mapping[account_id]
        x = self.data.x.clone().detach().requires_grad_(True)

        out, _ = self.model(x, self.data.edge_index)
        target_score = out[idx, 1]

        target_score.backward()
        grad = x.grad[idx]
        attr = (grad * x[idx]).detach().numpy()

        # Format attributions
        attributions = []
        for feat_name, val, score in zip(FEATURE_NAMES, x[idx].numpy(), attr):
            attributions.append({
                "feature": feat_name,
                "value": float(val),
                "importance": float(abs(score)),
                "direction": "POSITIVE_RISK" if score > 0 else "BENIGN"
            })

        attributions.sort(key=lambda x: x["importance"], reverse=True)

        return {
            "account_id": account_id,
            "mule_probability": float(torch.softmax(out[idx], dim=0)[1].item()),
            "top_drivers": attributions[:5],
            "all_features": attributions,
        }
