"""
MuleTrace — Sanctions & High-Risk Jurisdiction Screener
"""

from typing import Dict, Any, List

HIGH_RISK_JURISDICTIONS = {
    "NG": {"name": "Nigeria", "risk_tier": "HIGH", "reason": "Elevated financial crime monitoring zone"},
    "RU": {"name": "Russia", "risk_tier": "HIGH", "reason": "International sanction sanctions list"},
    "PH": {"name": "Philippines", "risk_tier": "MEDIUM", "reason": "Increased FATF monitoring jurisdiction"},
}


class SanctionsScreener:
    def screen_account(self, account_id: str, account_data: Dict[str, Any]) -> Dict[str, Any]:
        jur = account_data.get("jurisdiction", "IN")
        is_sanctioned = jur in HIGH_RISK_JURISDICTIONS

        if is_sanctioned:
            info = HIGH_RISK_JURISDICTIONS[jur]
            return {
                "account_id": account_id,
                "is_sanction_match": True,
                "jurisdiction": jur,
                "jurisdiction_name": info["name"],
                "risk_tier": info["risk_tier"],
                "reason": info["reason"],
            }

        return {
            "account_id": account_id,
            "is_sanction_match": False,
            "jurisdiction": jur,
            "risk_tier": "LOW",
            "reason": "Standard jurisdiction compliance check passed."
        }
