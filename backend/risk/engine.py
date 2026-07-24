"""
MuleTrace — Risk Intelligence Engine
"""

import networkx as nx
from typing import List, Dict, Any
from backend.risk.patterns import PatternDetector


class RiskIntelligenceEngine:
    def __init__(self, G: nx.DiGraph, risk_scores: List[Dict[str, Any]]):
        self.G = G
        self.risk_scores = risk_scores
        self.pattern_detector = PatternDetector(G)

    def analyze(() -> Dict[str, Any]:
        """Combine GNN risk scores with pattern detection results."""
        flagged_accs = [r for r in self.risk_scores if r["is_flagged"]]
        high_risk_accs = [r for r in self.risk_scores if r["risk_level"] == "HIGH"]

        structuring = self.pattern_detector.detect_structuring()
        rapid_cashouts = self.pattern_detector.detect_rapid_cashout()
        clusters = self.pattern_detector.detect_mule_clusters()

        risk_dist = {
            "HIGH": len(high_risk_accs),
            "MEDIUM": len(flagged_accs) - len(high_risk_accs),
            "LOW": len(self.risk_scores) - len(flagged_accs)
        }

        return {
            "total_accounts_analyzed": len(self.risk_scores),
            "flagged_accounts": len(flagged_accs),
            "high_risk_accounts": high_risk_accs[:15],
            "risk_distribution": risk_dist,
            "structuring_events": structuring[:10],
            "rapid_cashouts": rapid_cashouts[:10],
            "mule_clusters": clusters[:10],
        }
