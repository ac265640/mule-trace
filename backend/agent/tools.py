"""
MuleTrace — Agentic Tool Registry

Modular tools invoked dynamically by the Agent Orchestrator:
  - EDA_Tool
  - Feature_Engineering_Tool
  - Anomaly_Detection_Tool
  - Risk_Classification_Tool
  - Explanation_Tool
  - Escalation_Tool
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List


class AgentToolRegistry:
    def __init__(self, data: Dict[str, pd.DataFrame] = None, G = None, risk_scores: List[Dict] = None):
        self.data = data
        self.G = G
        self.risk_scores = risk_scores or []

    def run_eda_tool(self) -> Dict[str, Any]:
        """Perform Exploratory Data Analysis profiling."""
        if not self.data:
            return {"status": "No data available for EDA"}

        tx_df = self.data["transactions"]
        acc_df = self.data["accounts"]

        channel_breakdown = tx_df["channel_type"].value_counts().to_dict()
        pattern_breakdown = tx_df["pattern_type"].value_counts().to_dict()

        return {
            "total_customers": len(acc_df),
            "total_transactions": len(tx_df),
            "total_volume_usd": float(tx_df["amount"].sum()),
            "average_transaction_amount": float(tx_df["amount"].mean()),
            "channel_breakdown": channel_breakdown,
            "pattern_breakdown": pattern_breakdown,
        }

    def run_structuring_tool(self, max_amount: float = 10000.0) -> List[Dict[str, Any]]:
        """Run structuring detection on sub-$10k transfers."""
        if not self.data:
            return []

        tx_df = self.data["transactions"]
        sub_10k = tx_df[(tx_df["amount"] >= 8000.0) & (tx_df["amount"] < max_amount)]

        results = []
        for _, row in sub_10k.iterrows():
            results.append({
                "transaction_id": row["transaction_id"],
                "source_account": row["source_account"],
                "target_account": row["target_account"],
                "amount": float(row["amount"]),
                "channel": row["channel_type"],
                "pattern": "STRUCTURING_SUB_10K",
                "explanation": f"Sub-threshold deposit of ${row['amount']:,.2f} evading $10,000 regulatory line."
            })
        return results

    def run_aggregation_rule_tool(self, threshold: float = 10000.0, min_count: int = 10) -> List[Dict[str, Any]]:
        """Run aggregation threshold rule directly without ML."""
        if not self.data:
            return []

        tx_df = self.data["transactions"]
        sub_10k = tx_df[tx_df["amount"] < threshold]

        counts = sub_10k.groupby("source_account").size()
        flagged_sources = counts[counts >= min_count].index.tolist()

        results = []
        for src in flagged_sources:
            cnt = int(counts[src])
            total_amt = float(sub_10k[sub_10k["source_account"] == src]["amount"].sum())
            results.append({
                "account_id": src,
                "sub_10k_tx_count": cnt,
                "total_volume": total_amt,
                "risk_tier": "HIGH",
                "recommended_action": "FLAG_FOR_REVIEW",
                "explanation": f"Customer executed {cnt} transactions under ${threshold:,.0f} totaling ${total_amt:,.2f}."
            })
        return results

    def run_single_entity_lookup(self, account_id: str) -> Dict[str, Any]:
        """Perform single entity lookup for specific customer ID."""
        matched_risk = next((r for r in self.risk_scores if r["account_id"] == account_id), None)

        if not matched_risk:
            matched_risk = {
                "account_id": account_id,
                "mule_probability": 0.15,
                "risk_level": "LOW",
                "recommended_action": "MONITOR"
            }

        return {
            "account_id": account_id,
            "risk_score": matched_risk["mule_probability"],
            "risk_tier": matched_risk["risk_level"],
            "recommended_action": matched_risk["recommended_action"],
            "explanation": f"Single entity audit for {account_id}: Risk tier classified as {matched_risk['risk_level']}."
        }
