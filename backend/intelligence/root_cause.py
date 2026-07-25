"""
ChainVigil — Root-Cause Explanation Engine  (STEP 4)

Why this exists:
  The existing MuleExplainer (xai/explainer.py) produces feature attributions,
  but returns a single long sentence.  Compliance teams need:
    - A bullet-point breakdown of WHAT triggered the flag
    - Combined context from GNN + rules + temporal + behavioral signals
    - A clear severity label

  This module takes all available signals and renders them into structured,
  human-readable explanations — without re-running the model.
"""

from typing import Any, Dict, List, Optional


# ── Severity mapping ──────────────────────────────────────────────────────────

def _risk_tier(score: float) -> str:
    if score >= 0.85:
        return "CRITICAL"
    if score >= 0.70:
        return "HIGH"
    if score >= 0.50:
        return "MEDIUM"
    return "LOW"


# ── Signal → readable text converters ────────────────────────────────────────

_FEATURE_TEMPLATES: Dict[str, str] = {
    "avg_velocity_seconds":    "High transaction velocity (rapid fund movement)",
    "shared_device_count":     "Device shared with multiple accounts",
    "shared_ip_count":         "IP address shared with multiple accounts",
    "clustering_coefficient":  "Dense inter-account connections (ring topology)",
    "pagerank":                "High network centrality — hub role in mule network",
    "channel_diversity":       "Transactions spread across multiple payment channels",
    "amount_ratio":            "Pass-through behavior (high outflow-to-inflow ratio)",
    "atm_withdrawal_count":    "Elevated ATM withdrawal activity",
    "in_degree":               "High incoming transaction count",
    "out_degree":              "High outgoing transaction count",
    "total_degree":            "Very high total transaction volume",
    "jurisdiction_risk_weight":"Transactions linked to high-risk jurisdictions",
}


class RootCauseEngine:
    """
    Aggregates all available signals into a structured explanation record.

    Input: results from GNN XAI, rule engine, temporal detector, behavioral profiler.
    Output: {
        "account_id":       str,
        "final_risk_score": float,
        "risk_tier":        str,
        "explanation":      [str, ...],   # human-readable bullet points
        "evidence":         {key: value}  # raw values for audit trail
    }
    """

    def explain(
        self,
        account_id: str,
        gnn_score: float,
        rule_reasons: Optional[List[str]] = None,
        xai_features: Optional[List[Dict]] = None,
        temporal_result: Optional[Dict] = None,
        behavioral_result: Optional[Dict] = None,
        nlp_result: Optional[Dict] = None,
        cluster_id: Optional[str] = None,
        high_risk_neighbors: int = 0,
    ) -> Dict[str, Any]:
        """
        Build the structured root-cause explanation.

        Parameters mirror the various module outputs so callers can pass
        only what they have — all parameters except account_id / gnn_score
        are optional.
        """
        bullets: List[str] = []
        evidence: Dict[str, Any] = {
            "gnn_score": round(gnn_score, 4),
            "cluster_id": cluster_id,
            "high_risk_neighbors": high_risk_neighbors,
        }

        # 1. Graph topology signals
        if high_risk_neighbors >= 3:
            bullets.append(
                f"Connected to {high_risk_neighbors} high-risk accounts"
            )
        if cluster_id:
            bullets.append(
                f"Member of mule ring cluster: {cluster_id}"
            )

        # 2. GNN-derived feature attributions (top features from XAI)
        if xai_features:
            for feat in xai_features[:3]:   # top 3 only, keep it concise
                name = feat.get("name", "")
                readable = _FEATURE_TEMPLATES.get(name, name.replace("_", " "))
                importance = feat.get("importance", 0)
                if importance > 0.05:        # skip near-zero attributions
                    bullets.append(readable)

        # 3. Rule engine reasons
        _rule_labels = {
            "very_high_amount":        "Transaction amount exceeds ₹1L threshold",
            "high_amount":             "Transaction amount exceeds ₹50K threshold",
            "high_value_atm":          "High-value ATM withdrawal detected",
            "rapid_outgoing_velocity": "Rapid outgoing transfers (≥5 in 10 minutes)",
            "moderate_outgoing_velocity": "Moderate velocity (≥3 tx in 10 minutes)",
            "circular_flow_signal":    "Circular money flow pattern detected",
            "known_high_risk_party":   "Transacted with a known high-risk account",
            "known_medium_risk_party": "Transacted with a medium-risk account",
            "self_transfer_detected":  "Self-transfer (hard block rule triggered)",
        }
        for r in (rule_reasons or []):
            label = _rule_labels.get(r, r.replace("_", " "))
            bullets.append(label)
        evidence["rule_reasons"] = rule_reasons or []

        # 4. Temporal signals
        if temporal_result:
            score_t = temporal_result.get("temporal_risk_score", 0)
            evidence["temporal_risk_score"] = score_t
            for sig in temporal_result.get("temporal_signals", []):
                bullets.append(sig)

        # 5. Behavioral signals
        if behavioral_result:
            score_b = behavioral_result.get("behavioral_risk_score", 0)
            evidence["behavioral_risk_score"] = score_b
            for sig in behavioral_result.get("behavioral_signals", []):
                bullets.append(sig)

        # 6. NLP signals
        if nlp_result and nlp_result.get("is_suspicious"):
            evidence["nlp_risk_score"] = nlp_result.get("nlp_risk_score", 0)
            matched = nlp_result.get("matched_patterns", [])
            if matched:
                bullets.append(
                    f"Suspicious text pattern in transaction note: "
                    f"{', '.join(matched[:3])}"
                )

        # Deduplicate while preserving order
        seen = set()  # type: ignore[var-annotated]
        unique_bullets = []
        for b in bullets:
            if b not in seen:
                seen.add(b)
                unique_bullets.append(b)

        # Compute final risk (weighted average of available scores)
        final_score = _weighted_final_score(
            gnn_score,
            temporal_result,
            behavioral_result,
            nlp_result,
        )

        return {
            "account_id": account_id,
            "final_risk_score": round(final_score, 4),
            "risk_tier": _risk_tier(final_score),
            "explanation": unique_bullets if unique_bullets
                           else ["Anomalous combination of signals detected"],
            "evidence": evidence,
        }


def _weighted_final_score(
    gnn: float,
    temporal: Optional[Dict],
    behavioral: Optional[Dict],
    nlp: Optional[Dict],
) -> float:
    """
    Combine module scores with weights.
    GNN is the anchor. If temporal/behavioral/nlp modules produce no signal
    (score == 0.0 with no detected signals), their weight is redistributed
    back to GNN so the final score stays consistent with the calibrated GNN score.
    """
    # Determine which supplementary modules actually produced a signal
    temporal_score = 0.0
    temporal_active = False
    if temporal:
        ts = temporal.get("temporal_risk_score", 0.0)
        has_signals = bool(temporal.get("temporal_signals")) or ts > 0
        if has_signals:
            temporal_score = ts
            temporal_active = True

    behavioral_score = 0.0
    behavioral_active = False
    if behavioral:
        bs = behavioral.get("behavioral_risk_score", 0.0)
        has_signals = bool(behavioral.get("behavioral_signals")) or bs > 0
        if has_signals:
            behavioral_score = bs
            behavioral_active = True

    nlp_score = 0.0
    nlp_active = False
    if nlp:
        ns = nlp.get("nlp_risk_score", 0.0)
        if ns > 0:
            nlp_score = ns
            nlp_active = True

    # Compute effective weights: redistribute unused module weights to GNN
    w_gnn = 1.0
    w_temporal = 0.0
    w_behavioral = 0.0
    w_nlp = 0.0

    if temporal_active:
        w_gnn -= 0.20
        w_temporal = 0.20
    if behavioral_active:
        w_gnn -= 0.15
        w_behavioral = 0.15
    if nlp_active:
        w_gnn -= 0.05
        w_nlp = 0.05

    score = (
        w_gnn * gnn
        + w_temporal * temporal_score
        + w_behavioral * behavioral_score
        + w_nlp * nlp_score
    )
    return min(1.0, round(score, 4))
