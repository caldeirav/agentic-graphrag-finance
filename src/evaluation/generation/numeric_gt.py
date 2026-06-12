"""Normalize numeric ground-truth answers for consistent judging and relevance."""

from __future__ import annotations

import re

_SCALE_WORDS = {
    "billion": 1e9,
    "bn": 1e9,
    "million": 1e6,
    "mm": 1e6,
    "m": 1e6,
    "thousand": 1e3,
    "k": 1e3,
}
_NUMERIC_GT = re.compile(
    r"^[\s$€£]*"
    r"(?:"
    r"-?\d+(?:\.\d+)?(?:\s*%|(?:\s*(?:billion|million|thousand|bn|mm|m|k))?)?"
    r"|"
    r"-?\d{1,3}(?:,\d{3})+(?:\.\d+)?(?:\s*%)?"
    r")"
    r"[\s$€£]*$",
    re.IGNORECASE,
)


def is_numeric_gt_string(answer: str) -> bool:
    return bool(_NUMERIC_GT.match((answer or "").strip()))


def parse_numeric_gt(answer: str) -> float | None:
    """Parse GT answer to a scalar (USD where currency implied, else raw number)."""
    text = (answer or "").strip().replace(",", "")
    if not text:
        return None
    is_percent = text.endswith("%")
    text = text.rstrip("%").strip()
    currency = bool(re.match(r"^[\s$€£]", text))
    text = re.sub(r"^[\s$€£]+", "", text).strip()

    scale = 1.0
    for word, mult in _SCALE_WORDS.items():
        pattern = rf"\s+{word}\s*$"
        if re.search(pattern, text, re.I):
            scale = mult
            text = re.sub(pattern, "", text, flags=re.I).strip()
            break

    try:
        value = float(text)
    except ValueError:
        return None

    if is_percent:
        return value
    if scale != 1.0:
        return value * scale
    if currency or value >= 1e6:
        return value
    return value


def normalize_numeric_gt(answer: str) -> str:
    """Canonical string form for bundle storage (compact decimal, no currency noise)."""
    parsed = parse_numeric_gt(answer)
    if parsed is None:
        return (answer or "").strip()
    if abs(parsed) >= 1e9:
        return f"{parsed:.0f}"
    if abs(parsed) >= 1e6:
        return f"{parsed:.0f}"
    if float(parsed).is_integer():
        return str(int(parsed))
    return f"{parsed:g}"


def numeric_values_equivalent(a: str, b: str, *, rel_tol: float = 0.02) -> bool:
    """True when two numeric GT strings refer to the same value within tolerance."""
    va = parse_numeric_gt(a)
    vb = parse_numeric_gt(b)
    if va is None or vb is None:
        return (a or "").strip() == (b or "").strip()
    if va == vb:
        return True
    denom = max(abs(va), abs(vb), 1.0)
    return abs(va - vb) / denom <= rel_tol


def xbrl_excerpt_matches_gt(excerpt: str, gt_answer: str) -> bool:
    """Match XBRL chunk excerpt text against numeric GT."""
    if not excerpt or not gt_answer:
        return False
    target = parse_numeric_gt(gt_answer)
    if target is None:
        return gt_answer.lower() in excerpt.lower()

    numbers = re.findall(r"-?\d+(?:\.\d+)?", excerpt.replace(",", ""))
    for raw in numbers:
        try:
            candidate = float(raw)
        except ValueError:
            continue
        if numeric_values_equivalent(str(candidate), gt_answer):
            return True
        if "billion" in excerpt.lower() and candidate * 1e9 == target:
            return True
        if "million" in excerpt.lower() and candidate * 1e6 == target:
            return True
    return False


def infer_xbrl_raw_value(gt_answer: str, decimals: str = "-6") -> str | None:
    """Infer raw XBRL integer from normalized GT for label matching."""
    parsed = parse_numeric_gt(gt_answer)
    if parsed is None:
        return None
    try:
        d = int(decimals)
    except ValueError:
        d = 0
    if d < 0:
        scaled = int(round(parsed / (10 ** (-d))))
        return str(scaled)
    return str(int(round(parsed)))
