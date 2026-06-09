"""Ground-truth classification helpers for custom-judge bundle migration (016)."""

from __future__ import annotations

import re

_NUMERIC_PATTERN = re.compile(
    r"^[\s$€£]*"
    r"(?:"
    r"-?\d+(?:\.\d+)?(?:\s*%|(?:\s*(?:billion|million|thousand|bn|mm|m|k))?)?"
    r"|"
    r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*%)?"
    r")"
    r"[\s$€£]*$",
    re.IGNORECASE,
)


def is_numeric_answer_gt(answer: str) -> bool:
    """True when answer GT is a single numeric/short-label target (no required_claims)."""
    text = (answer or "").strip()
    if not text:
        return False
    if _NUMERIC_PATTERN.match(text):
        return True
    tokens = text.split()
    if len(tokens) <= 4 and not any(
        tok.lower() in {"is", "are", "was", "were", "has", "have", "had", "the", "and", "that"}
        for tok in tokens
    ):
        return True
    return False
