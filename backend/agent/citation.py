"""
MuleTrace — Evidence Registry & Citation Enforcer

Every claim the agent makes must be traceable to a concrete evidence record
(a rule definition, a dataset aggregate, a transaction, or a model score).
The narrative cites evidence inline as [E1], [E2], ...

The enforcer is a post-generation validation layer: it runs AFTER the
narrative is composed and BEFORE it reaches the analyst. If any check fails
the answer is withheld and the agent refuses instead.

Checks:
  1. Confidence threshold — below it, the agent declines rather than guess.
  2. Minimum citations — an uncited answer cannot be verified.
  3. Citation validity — every cited id must exist in the evidence registry
     (catches hallucinated citations).
  4. Claim coverage — every sentence that states a number must cite evidence.
  5. Numeric grounding — every number in a sentence must appear in the
     evidence that sentence cites (catches fabricated figures).
"""

import re
from typing import Any, Dict, List, Optional

DEFAULT_CONFIDENCE_THRESHOLD = 0.3
MIN_CITATIONS = 1

CITATION_RE = re.compile(r"\[(E\d+)\]")
# Record identifiers (ACC-00001, TXN-3F3C..., MULE_RING_05) carry digits that are not claims.
IDENTIFIER_RE = re.compile(r"\b[A-Z][A-Z_]*-[A-Za-z0-9_-]+\b|\b[A-Z]+_[A-Z_]*\d+\b")
NUMBER_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class EvidenceRegistry:
    """Collects evidence records and hands out stable citation ids."""

    def __init__(self) -> None:
        self._items: List[Dict[str, Any]] = []

    def add(self, kind: str, source: str, label: str, data: Dict[str, Any]) -> str:
        eid = f"E{len(self._items) + 1}"
        self._items.append({"id": eid, "kind": kind, "source": source, "label": label, "data": data})
        return eid

    def ids(self) -> set:
        return {e["id"] for e in self._items}

    def get(self, eid: str) -> Optional[Dict[str, Any]]:
        return next((e for e in self._items if e["id"] == eid), None)

    def to_list(self) -> List[Dict[str, Any]]:
        return list(self._items)


class EnforcementResult:
    def __init__(self) -> None:
        self.is_valid: bool = True
        self.errors: List[str] = []
        self.hallucinated_ids: List[str] = []
        self.uncited_claims: List[str] = []
        self.ungrounded_numbers: List[Dict[str, str]] = []
        self.valid_citation_count: int = 0
        self.total_citation_count: int = 0
        self.claims_checked: int = 0

    def add_error(self, error: str) -> None:
        self.is_valid = False
        self.errors.append(error)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "hallucinated_ids": self.hallucinated_ids,
            "uncited_claims": self.uncited_claims,
            "ungrounded_numbers": self.ungrounded_numbers,
            "valid_citation_count": self.valid_citation_count,
            "total_citation_count": self.total_citation_count,
            "claims_checked": self.claims_checked,
        }


def _numeric_values(obj: Any) -> List[float]:
    """Flatten every numeric value found in an evidence payload."""
    out: List[float] = []
    if isinstance(obj, bool):
        return out
    if isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            out.extend(_numeric_values(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_numeric_values(v))
    return out


def _is_grounded(number: float, values: List[float]) -> bool:
    """A stated number is grounded if it matches an evidence value, allowing
    for display rounding and fraction-to-percent conversion (0.2305 -> 23.1%)."""
    for v in values:
        for candidate in (v, v * 100):
            if abs(number - candidate) <= max(0.051, 0.005 * abs(candidate)):
                return True
    return False


class CitationEnforcer:
    def __init__(
        self,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
        min_citations: int = MIN_CITATIONS,
    ) -> None:
        self.confidence_threshold = confidence_threshold
        self.min_citations = min_citations

    def enforce(self, narrative: str, confidence: float, registry: EvidenceRegistry) -> EnforcementResult:
        result = EnforcementResult()
        valid_ids = registry.ids()

        # Check 1: Confidence threshold
        if confidence < self.confidence_threshold:
            result.add_error(
                f"Confidence {confidence:.2f} below threshold {self.confidence_threshold:.2f}"
            )

        # Check 2 & 3: citation count and validity
        cited = CITATION_RE.findall(narrative)
        result.total_citation_count = len(cited)
        if len(cited) < self.min_citations:
            result.add_error(f"Only {len(cited)} citations, minimum required: {self.min_citations}")
        for eid in cited:
            if eid in valid_ids:
                result.valid_citation_count += 1
            elif eid not in result.hallucinated_ids:
                result.hallucinated_ids.append(eid)
                result.add_error(f"Hallucinated citation: [{eid}] not found in evidence registry")

        # Check 4 & 5: sentence-level claim coverage and numeric grounding
        for sentence in SENTENCE_RE.split(narrative.strip()):
            if not sentence:
                continue
            sentence_ids = [e for e in CITATION_RE.findall(sentence) if e in valid_ids]
            claim_text = IDENTIFIER_RE.sub("", CITATION_RE.sub("", sentence))
            numbers = NUMBER_RE.findall(claim_text)
            if not numbers:
                continue
            result.claims_checked += 1

            if not sentence_ids:
                result.uncited_claims.append(sentence)
                result.add_error(f"Uncited claim: \"{sentence[:80]}\"")
                continue

            values: List[float] = []
            for eid in sentence_ids:
                values.extend(_numeric_values(registry.get(eid)["data"]))
            for raw in numbers:
                if not _is_grounded(float(raw.replace(",", "")), values):
                    result.ungrounded_numbers.append({"value": raw, "sentence": sentence})
                    result.add_error(
                        f"Ungrounded figure '{raw}' not found in cited evidence {', '.join(sentence_ids)}"
                    )

        return result
