"""
MuleTrace — FIU-IND Compliant Suspicious Activity Report (SAR) Generator
"""

from datetime import datetime
from typing import Dict, Any


class AuditReportGenerator:
    def generate_sar_report(self, risk_summary: Dict[str, Any], account_explanations: Dict[str, Any] = None) -> Dict[str, Any]:
        """Generate official FIU-IND compliant SAR report payload."""
        timestamp = datetime.now().isoformat() + "Z"
        high_risk_list = risk_summary.get("high_risk_accounts", [])

        subjects = []
        for acc in high_risk_list[:10]:
            acc_id = acc["account_id"]
            expl = account_explanations.get(acc_id, {}) if account_explanations else {}
            top_drivers = [d["feature"] for d in expl.get("top_drivers", [])[:3]]

            subjects.append({
                "subject_id": acc_id,
                "mule_probability": acc.get("mule_probability", 0.0),
                "risk_tier": acc.get("risk_level", "HIGH"),
                "recommended_action": acc.get("recommended_action", "FILE_SAR_REPORT"),
                "primary_risk_factors": top_drivers or ["Sub-$10k Structuring", "Shared Device Cluster"],
            })

        return {
            "report_header": {
                "report_type": "FIU-IND SUSPICIOUS ACTIVITY REPORT (SAR)",
                "regulatory_authority": "Financial Intelligence Unit - Anti Money Laundering",
                "generated_at": timestamp,
                "system_name": "MuleTrace Autonomous AML Agent",
            },
            "summary_statistics": {
                "total_accounts_audited": risk_summary.get("total_accounts_analyzed", 0),
                "flagged_suspicious_accounts": risk_summary.get("flagged_accounts", 0),
                "structuring_events_detected": len(risk_summary.get("structuring_events", [])),
                "mule_clusters_detected": len(risk_summary.get("mule_clusters", [])),
            },
            "flagged_subjects": subjects,
            "escalation_protocol": {
                "next_action": "SUBMIT_TO_COMPLIANCE_OFFICER",
                "mandatory_freeze_threshold": 0.85,
                "review_deadline_hours": 24,
            }
        }
