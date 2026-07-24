"""
MuleTrace — GNN Inference & Mule Risk Scoring Engine
"""

import torch
from typing import List, Dict, Any


def predict_scores(model, data, account_ids: List[str]) -> List[Dict[str, Any]]:
    """Generate risk probabilities for all account nodes using trained GNN model."""
    model.eval()
    with torch.no_grad():
        out, _ = model(data.x, data.edge_index)
        probs = torch.softmax(out, dim=1)[:, 1].numpy()

    results = []
    for i, acc_id in enumerate(account_ids):
        prob = float(probs[i])

        if prob >= 0.75:
            risk_level = "HIGH"
            rec_action = "FILE_SAR_REPORT"
        elif prob >= 0.40:
            risk_level = "MEDIUM"
            rec_action = "FLAG_FOR_REVIEW"
        else:
            risk_level = "LOW"
            rec_action = "MONITOR"

        results.append({
            "account_id": acc_id,
            "mule_probability": prob,
            "risk_level": risk_level,
            "recommended_action": rec_action,
            "is_flagged": prob >= 0.40,
        })

    # Sort descending by risk score
    results.sort(key=lambda x: x["mule_probability"], reverse=True)
    return results
