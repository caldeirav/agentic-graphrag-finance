"""Comparison-structured ground truth validation for custom-judge v2.0 (017)."""

from __future__ import annotations

import re

from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem

_BOTH_FILINGS_PATTERN = re.compile(
    r"both\s+.+\s+and\s+.+\s+(discuss|address|describe|mention|cover)",
    re.IGNORECASE,
)


def is_comparison_item(item: GeneratedBenchmarkItem) -> bool:
    if item.answer_type == AnswerType.COMPARISON_STRUCTURED:
        return True
    tag = (item.question_type_tag or "").lower()
    return any(
        kw in tag
        for kw in ("comparison", "multi-hop", "cross-filing", "agentic-multi")
    )


def validate_comparison_structured(item: GeneratedBenchmarkItem) -> list[str]:
    """Return validation error codes for comparison_structured items."""
    errors: list[str] = []
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    if not answer:
        errors.append("missing_answer_gt")
        return errors
    if not _BOTH_FILINGS_PATTERN.search(answer):
        errors.append("invalid_answer_type")
    accs = list(dict.fromkeys(item.expected_bindings.accessions))
    if len(accs) < 2:
        errors.append("comparison_bindings")
    claims = [c.strip() for c in (gt.required_claims or []) if c and c.strip()]
    if len(claims) < 3:
        errors.append("required_claims")
        return errors
    if len(claims) > 8:
        errors.append("required_claims")
    filing_claims = [c for c in claims if re.search(r"\b10-[KQ]\b|FY20\d{2}", c, re.I)]
    if len(filing_claims) < 2:
        errors.append("required_claims")
    cross = [c for c in claims if "comparison spans" in c.lower() or "both bound" in c.lower()]
    if not cross:
        errors.append("required_claims")
    return errors


def derive_comparison_claims(answer: str, *, label_a: str, label_b: str, topic: str, section: str) -> list[str]:
    """Build minimum claim set from canonical comparison answer template."""
    section_text = section.strip() or "the cited sections"
    return [
        f"{label_a} discusses {topic} in {section_text}.",
        f"{label_b} discusses {topic} in {section_text}.",
        "The comparison spans both bound filings.",
    ]
