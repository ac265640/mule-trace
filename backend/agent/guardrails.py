"""
MuleTrace — Agent Guardrails (refuse-to-answer layer)

Three gates around the agent, checked in order:

  1. Input guard (before planning) — refuses prompt injection, requests to
     evade AML controls or tip off subjects, requests for customer personal
     data, and anything outside the AML investigation domain.
     Safety is checked before scope: safety overrides utility.

  2. Pre-generation decline (after planning, before tools) — refuses when
     there is nothing to ground an answer in: no dataset, no trained model,
     no account id for an entity audit, or an account that does not exist.
     Better to say "I don't know" than to fabricate a risk profile.

  3. Output guard (after citation enforcement) — scrubs PII that could leak
     into the narrative and appends an analyst-review disclaimer.
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

SUGGESTED_QUERIES = [
    "Find structuring patterns in the last 30 days",
    "Which customers made 10+ transactions under $10,000?",
    "Is customer ACC-00001 suspicious?",
    "Scan for rapid cash-out velocity anomalies",
]

# ── 1. Input guard ────────────────────────────────────────────────────────────

PROMPT_INJECTION_PATTERNS = [
    re.compile(r"\bignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules|prompts?)\b", re.I),
    re.compile(r"\b(reveal|show|print|repeat)\s+(your|the)\s+(system\s+prompt|instructions|rules)\b", re.I),
    re.compile(r"\byou\s+are\s+now\b|\bact\s+as\s+(a|an)\b|\bdeveloper\s+mode\b|\bjailbreak\b", re.I),
    re.compile(r"\b(disable|turn\s+off|bypass)\s+(your\s+)?(guardrails?|safety|filters?|citations?)\b", re.I),
]

# Requests for help committing or concealing financial crime, or alerting a subject.
EVASION_PATTERNS = [
    re.compile(r"\bhow\s+(to|can\s+i|do\s+i|would\s+i|should\s+i|could\s+i)\s+(evade|bypass|avoid|beat|get\s+around|launder|hide|structure|split)\b", re.I),
    re.compile(r"\bhelp\s+me\s+(launder|structure|evade|hide|move|clean|split)\b", re.I),
    re.compile(r"\bwithout\s+(getting\s+|being\s+)?(flagged|caught|detected|reported|noticed)\b", re.I),
    re.compile(r"\b(stay|keep\s+\w+)\s+under\s+the\s+(radar|reporting\s+threshold)\b", re.I),
    re.compile(r"\b(tip(ping)?\s+off|warn|alert|notify)\s+(the\s+)?(customer|subject|account\s+holder|suspect)\b", re.I),
]

INVESTMENT_ADVICE_PATTERNS = [
    re.compile(r"\bshould\s+i\s+(buy|sell|invest|hold)\b", re.I),
    re.compile(r"\b(investment|financial)\s+advice\b|\bbest\s+(stock|investment|crypto|fund)\b", re.I),
]

# Identity data stays out of the agent channel; analysts use the case system for KYC lookups.
PII_REQUEST_PATTERNS = [
    re.compile(r"\b(holder|customer|account\s+holder'?s?|owner'?s?)\s+(full\s+)?(name|address|phone|email|dob|date\s+of\s+birth)\b", re.I),
    re.compile(r"\b(ssn|social\s+security|aadhaar|pan\s+number|passport\s+number|kyc\s+documents?)\b", re.I),
    re.compile(r"\b(who\s+owns|name\s+of\s+the\s+(owner|holder|customer))\b", re.I),
    re.compile(r"\bpersonal\s+(details|data|information)\b", re.I),
]

DOMAIN_TERMS = re.compile(
    r"acc-\d|\b(structur\w*|smurf\w*|mule\w*|launder\w*|aml|suspicious|fraud\w*|risk\w*|account\w*|"
    r"customer\w*|transaction\w*|transfer\w*|threshold\w*|cash\w*|atm|velocity|eda|profil\w*|"
    r"distribution\w*|channel\w*|upi|ring\w*|cluster\w*|device\w*|network\w*|sar|ctr|anomal\w*|"
    r"flag\w*|deposit\w*|withdraw\w*|payment\w*|scan\w*|pattern\w*|volume\w*|graph|gnn|"
    r"escalat\w*|alert\w*|sanction\w*|layering|money)\b",
    re.I,
)


def _first_match(patterns: Iterable[re.Pattern], text: str) -> Optional[str]:
    for p in patterns:
        m = p.search(text)
        if m:
            return m.group(0)
    return None


def build_refusal(category: str, reason: str, details: Optional[List[str]] = None,
                  suggestions: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "category": category,
        "reason": reason,
        "details": details or [],
        "suggestions": SUGGESTED_QUERIES if suggestions is None else suggestions,
    }


def run_input_guards(query: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (refusal or None, list of check results for the trace)."""
    checks: List[Dict[str, Any]] = []

    def check(name: str, patterns, category: str, reason: str):
        hit = _first_match(patterns, query)
        checks.append({"guard": name, "passed": hit is None, **({"matched": hit} if hit else {})})
        if hit:
            return build_refusal(category, reason, [f"Matched: \"{hit}\""])
        return None

    refusal = (
        check("prompt_injection", PROMPT_INJECTION_PATTERNS, "PROMPT_INJECTION",
              "This request tries to change how the agent operates. Its guardrails and citation rules cannot be overridden from a query.")
        or check("aml_evasion", EVASION_PATTERNS, "PROHIBITED_REQUEST",
                 "I can't help evade AML controls, conceal funds, or alert a subject under investigation. I can help detect these behaviours instead.")
        or check("investment_advice", INVESTMENT_ADVICE_PATTERNS, "OUT_OF_SCOPE",
                 "I'm an AML investigation assistant and don't give investment or financial advice.")
        or check("pii_request", PII_REQUEST_PATTERNS, "PII_REQUEST",
                 "I don't disclose customer identity data (names, contact details, ID numbers). I can share account IDs, risk scores, and transaction evidence.")
    )
    if refusal:
        return refusal, checks

    in_scope = bool(DOMAIN_TERMS.search(query))
    checks.append({"guard": "domain_scope", "passed": in_scope})
    if not in_scope:
        return build_refusal(
            "OUT_OF_SCOPE",
            "This question is outside what I can answer. I investigate suspicious activity in this bank's transaction data: structuring, threshold evasion, rapid cash-outs, mule rings, and individual account risk.",
        ), checks

    return None, checks


# ── 2. Pre-generation decline ────────────────────────────────────────────────

MODEL_INTENTS = {"SINGLE_ENTITY_LOOKUP", "HYBRID_PATTERN_SCAN"}


def should_decline(intent: str, target_entity: Optional[str], data: Optional[Dict[str, Any]],
                   risk_scores: List[Dict[str, Any]], G=None) -> Optional[Dict[str, Any]]:
    """Decline before running tools when no grounded answer is possible."""
    if not data or "transactions" not in data or "accounts" not in data:
        return build_refusal(
            "NO_DATA",
            "No transaction dataset is loaded, so there is no evidence to answer from.",
            suggestions=[],
        ) | {"next_step": "Run the pipeline from the Pipeline Engine tab, then ask again."}

    if intent in MODEL_INTENTS and not risk_scores:
        return build_refusal(
            "MODEL_NOT_READY",
            "This question needs GNN risk scores, but the model hasn't been trained in this session.",
            suggestions=[q for q in SUGGESTED_QUERIES if "ACC-" not in q],
        ) | {"next_step": "Click Run Full Pipeline on the Pipeline Engine tab, then ask again."}

    if intent == "SINGLE_ENTITY_LOOKUP":
        if not target_entity:
            return build_refusal(
                "MISSING_ENTITY",
                "An entity audit needs an account ID, and I couldn't find one in your question. I won't guess which account you mean.",
                suggestions=["Is customer ACC-00001 suspicious?"],
            )
        known = any(r.get("account_id") == target_entity for r in risk_scores)
        in_data = bool((data["accounts"]["account_id"] == target_entity).any())
        if not known and not in_data:
            return build_refusal(
                "ENTITY_NOT_FOUND",
                f"{target_entity} does not exist in the loaded dataset, so I have no evidence about it.",
                [f"Searched {len(data['accounts']):,} accounts and {len(risk_scores):,} risk scores."],
                suggestions=[f"Is customer {r['account_id']} suspicious?" for r in risk_scores[:2]] or None,
            )
        if not known:
            return build_refusal(
                "INSUFFICIENT_EVIDENCE",
                f"{target_entity} exists but has no model risk score, so I can't assess it.",
            )
    return None


# ── 3. Output guard ──────────────────────────────────────────────────────────

OUTPUT_PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN REDACTED]"),
    (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "[CARD REDACTED]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL REDACTED]"),
    (re.compile(r"\+?\b\d{2,3}[ -]?\d{4,5}[ -]?\d{4,5}\b"), "[PHONE REDACTED]"),
]

ANALYST_DISCLAIMER = (
    "Decision support only. Findings come from rules and model scores on this dataset "
    "and must be verified by an analyst before any SAR filing or account action."
)


def run_output_guards(text: str, holder_names: Iterable[str] = ()) -> Dict[str, Any]:
    redactions = 0
    for pattern, marker in OUTPUT_PII_PATTERNS:
        text, n = pattern.subn(marker, text)
        redactions += n
    for name in holder_names:
        if name and name in text:
            redactions += text.count(name)
            text = text.replace(name, "[NAME REDACTED]")
    return {"text": text, "redactions": redactions, "disclaimer": ANALYST_DISCLAIMER}
