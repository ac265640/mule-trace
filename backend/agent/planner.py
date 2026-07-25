"""
MuleTrace — NLP Intent Parser & Dynamic Execution Planner

Parses natural language user queries, extracts intent, date/amount filters,
entity targets, and builds a dynamic step-by-step execution plan invoking
ONLY the necessary tools.
"""

import re
from typing import Dict, Any, List


class AgentPlanner:
    def parse_query(self, query: str, strategy: str = None) -> Dict[str, Any]:
        """Parse natural language query into intent, filters, entities, and execution plan."""
        query_lower = query.lower()

        intent = "HYBRID_PATTERN_SCAN"
        filters = {}
        target_entity = None

        # Strategy dropdown override (if explicitly selected by analyst)
        if strategy == "Structuring Scan":
            intent = "STRUCTURING_DETECTION"
            filters["max_amount"] = 10000.0
            filters["min_amount"] = 8000.0
        elif strategy == "Fast Rule Engine":
            intent = "AGGREGATION_THRESHOLD"
            filters["threshold_amount"] = 10000.0
            filters["min_count"] = 10
        elif strategy == "Single Entity Audit":
            intent = "SINGLE_ENTITY_LOOKUP"
            acc_match = re.search(r"acc-\d{5}|customer\s*(id\s*)?(\d{4,5})", query_lower)
            if acc_match:
                if "acc-" in acc_match.group(0):
                    target_entity = acc_match.group(0).upper()
                else:
                    digits = re.search(r"\d+", acc_match.group(0)).group(0)
                    target_entity = f"ACC-{int(digits):05d}"
            else:
                target_entity = "ACC-00001"
        else:
            # Automatic NLP Intent Resolution
            acc_match = re.search(r"acc-\d{5}|customer\s*(id\s*)?(\d{4,5})", query_lower)
            if acc_match:
                intent = "SINGLE_ENTITY_LOOKUP"
                if "acc-" in acc_match.group(0):
                    target_entity = acc_match.group(0).upper()
                else:
                    digits = re.search(r"\d+", acc_match.group(0)).group(0)
                    target_entity = f"ACC-{int(digits):05d}"

            elif any(w in query_lower for w in ["10+ ", "10 or more", "10+ transactions", "made 10", "frequency", "multiple transactions", "how many"]):
                intent = "AGGREGATION_THRESHOLD"
                filters["threshold_amount"] = 10000.0
                filters["min_count"] = 10

            elif any(w in query_lower for w in ["structuring", "smurf", "sub 10k", "<10k", "< 10000", "9000", "pattern"]):
                intent = "STRUCTURING_DETECTION"
                filters["max_amount"] = 10000.0
                filters["min_amount"] = 8000.0

            elif any(w in query_lower for w in ["eda", "profile", "distribution", "breakdown", "explore", "automated eda"]):
                intent = "BROAD_EDA_EXPLORATION"

            elif any(w in query_lower for w in ["rapid", "cashout", "cash-out", "velocity", "atm"]):
                intent = "RAPID_CASHOUT_VELOCITY"

        # Construct Dynamic Plan Steps
        plan_steps = self._construct_plan_steps(intent, filters, target_entity)

        return {
            "query": query,
            "detected_intent": intent,
            "filters": filters,
            "target_entity": target_entity,
            "plan_steps": plan_steps,
        }

    def _construct_plan_steps(self, intent: str, filters: Dict[str, Any], target_entity: str) -> List[Dict[str, str]]:
        if intent == "STRUCTURING_DETECTION":
            return [
                {"step": 1, "tool": "Filter_Data_Tool", "reason": "Apply $10,000 regulatory reporting filter"},
                {"step": 2, "tool": "Feature_Engineering_Tool", "reason": "Calculate sub-threshold velocity features"},
                {"step": 3, "tool": "Anomaly_Detection_Tool", "reason": "Run statistical IQR anomaly detection on sub-threshold transfers"},
                {"step": 4, "tool": "Explanation_Tool", "reason": "Generate natural language XAI reasons for structuring flags"}
            ]
        elif intent == "AGGREGATION_THRESHOLD":
            return [
                {"step": 1, "tool": "Filter_Data_Tool", "reason": "Filter transactions under $10,000"},
                {"step": 2, "tool": "Aggregation_Rule_Tool", "reason": "Count transactions per customer against frequency threshold (>=10)"},
                {"step": 3, "tool": "Escalation_Tool", "reason": "Assign review escalation status for threshold breach"}
            ]
        elif intent == "SINGLE_ENTITY_LOOKUP":
            return [
                {"step": 1, "tool": "Entity_Lookup_Tool", "reason": f"Perform direct single-entity lookup for {target_entity}"},
                {"step": 2, "tool": "Graph_Neighbor_Tool", "reason": "Retrieve connected devices, IPs, and transfer history"},
                {"step": 3, "tool": "Explanation_Tool", "reason": "Compute on-demand XAI attribution and risk score"}
            ]
        elif intent == "BROAD_EDA_EXPLORATION":
            return [
                {"step": 1, "tool": "EDA_Tool", "reason": "Compute exploratory data profiling, channel distributions, and summary stats"},
                {"step": 2, "tool": "Risk_Classification_Tool", "reason": "Map baseline customer segment risk distribution"}
            ]
        else:
            return [
                {"step": 1, "tool": "EDA_Tool", "reason": "Run broad transaction profiling"},
                {"step": 2, "tool": "Feature_Engineering_Tool", "reason": "Compute 10+ topological & financial features"},
                {"step": 3, "tool": "GNN_Anomaly_Tool", "reason": "Execute GraphSAGE+GAT PyTorch Geometric neural network inference"},
                {"step": 4, "tool": "Risk_Classification_Tool", "reason": "Classify accounts into Low, Medium, and High risk tiers"},
                {"step": 5, "tool": "Explanation_Tool", "reason": "Generate GradientxInput XAI explanations and escalation recommendations"}
            ]
