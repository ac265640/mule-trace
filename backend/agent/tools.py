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

        channel_breakdown = tx_df["channel_type"].value_counts().to_dict() if "channel_type" in tx_df.columns else {}

        # pattern_type may not exist in current dataset schema — use is_suspicious instead
        if "pattern_type" in tx_df.columns:
            pattern_breakdown = tx_df["pattern_type"].value_counts().to_dict()
        elif "is_suspicious" in tx_df.columns:
            pattern_breakdown = {
                "suspicious": int(tx_df["is_suspicious"].sum()),
                "normal": int((~tx_df["is_suspicious"]).sum()),
            }
        else:
            pattern_breakdown = {}

        # Typology breakdown from mule rings metadata if available
        mule_prevalence = None
        if "is_mule" in acc_df.columns:
            mule_count = int(acc_df["is_mule"].sum())
            total = len(acc_df)
            mule_prevalence = {
                "mule_accounts": mule_count,
                "total_accounts": total,
                "prevalence_pct": round(mule_count / total * 100, 2) if total > 0 else 0,
            }

        return {
            "total_customers": len(acc_df),
            "total_transactions": len(tx_df),
            "total_volume_usd": float(tx_df["amount"].sum()),
            "average_transaction_amount": float(tx_df["amount"].mean()),
            "channel_breakdown": channel_breakdown,
            "pattern_breakdown": pattern_breakdown,
            "mule_prevalence": mule_prevalence,
        }


    def run_structuring_tool(self, max_amount: float = 10000.0) -> List[Dict[str, Any]]:
        """Run structuring detection on sub-$10k transfers."""
        if not self.data or "transactions" not in self.data:
            return []

        tx_df = self.data["transactions"]
        src_col = "source_id" if "source_id" in tx_df.columns else "source_account"
        tgt_col = "target_id" if "target_id" in tx_df.columns else "target_account"

        sub_10k = tx_df[(tx_df["amount"] >= 8000.0) & (tx_df["amount"] < max_amount)]

        results = []
        for _, row in sub_10k.iterrows():
            results.append({
                "transaction_id": row.get("transaction_id", "N/A"),
                "source_account": row.get(src_col, "UNKNOWN"),
                "target_account": row.get(tgt_col, "UNKNOWN"),
                "amount": float(row["amount"]),
                "channel": row.get("channel_type", "ONLINE"),
                "pattern": "STRUCTURING_SUB_10K",
                "explanation": f"Sub-threshold deposit of ${row['amount']:,.2f} evading $10,000 regulatory line."
            })
        return results

    def run_aggregation_rule_tool(self, threshold: float = 10000.0, min_count: int = 10) -> List[Dict[str, Any]]:
        """Run aggregation threshold rule directly without ML."""
        if not self.data or "transactions" not in self.data:
            return []

        tx_df = self.data["transactions"]
        src_col = "source_id" if "source_id" in tx_df.columns else "source_account"

        sub_10k = tx_df[tx_df["amount"] < threshold]

        counts = sub_10k.groupby(src_col).size()
        flagged_sources = counts[counts >= min_count].index.tolist()

        results = []
        for src in flagged_sources:
            cnt = int(counts[src])
            total_amt = float(sub_10k[sub_10k[src_col] == src]["amount"].sum())
            results.append({
                "account_id": str(src),
                "sub_10k_tx_count": cnt,
                "total_volume": total_amt,
                "risk_tier": "HIGH",
                "recommended_action": "FLAG_FOR_REVIEW",
                "explanation": f"Customer executed {cnt} transactions under ${threshold:,.0f} totaling ${total_amt:,.2f}."
            })
        return results

    def run_single_entity_lookup(self, account_id: str) -> Dict[str, Any]:
        """Perform single entity lookup for specific customer ID."""
        matched_risk = next((r for r in self.risk_scores if r.get("account_id") == account_id), None)

        if matched_risk:
            prob = matched_risk.get("mule_probability", 0.5)
            tier = matched_risk.get("risk_tier") or matched_risk.get("risk_level") or ("HIGH" if prob >= 0.7 else "MEDIUM" if prob >= 0.4 else "LOW")
            action = matched_risk.get("recommended_action") or matched_risk.get("action") or "MONITOR"
        else:
            prob = 0.15
            tier = "LOW"
            action = "MONITOR"

        return {
            "account_id": account_id,
            "mule_probability": prob,   # key matches orchestrator + predict_scores schema
            "risk_score": prob,         # keep for any other callers
            "risk_tier": tier,
            "recommended_action": action,
            "explanation": f"Single entity audit for {account_id}: Risk tier classified as {tier}."
        }

