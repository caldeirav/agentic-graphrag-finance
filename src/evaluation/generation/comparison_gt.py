"""Comparison-structured ground truth validation for custom-judge v2.0 (017)."""

from __future__ import annotations

import re

from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem

_BOTH_FILINGS_PATTERN = re.compile(
    r"both\s+.+\s+and\s+.+\s+(discuss|address|describe|mention|cover)",
    re.IGNORECASE,
)
_FILING_ANCHOR = re.compile(r"\b(?:FY)?(20\d{2})\s+10-[KQ]\b|\bFY20\d{2}\b", re.IGNORECASE)
_ENTITY_STOP = frozenset(
    {"inc", "corp", "corporation", "company", "ltd", "llc", "plc", "the", "and", "for"}
)
_CROSS_VERB = re.compile(
    r"\b(compare|comparison|contrast|compared|versus|vs\.?|whereas|"
    r"similar|differ|difference|shared|common|in common|relative to)\b",
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


def extract_comparison_entities(answer: str) -> tuple[str | None, str | None]:
    """Parse the two compared entities from a canonical comparison answer."""
    text = (answer or "").strip()
    if not text:
        return None, None
    match = re.search(
        r"both\s+(.+?)\s+and\s+(.+?)\s+(?:'s\s+)?(?:\d{4}\s+)?10-[KQ]",
        text,
        re.IGNORECASE,
    )
    if match:
        return _normalize_entity(match.group(1)), _normalize_entity(match.group(2))
    match = _BOTH_FILINGS_PATTERN.search(text)
    if match:
        prefix = match.group(0)
        inner = re.match(r"both\s+(.+?)\s+and\s+(.+?)\s+(?:discuss|address|describe|mention|cover)", prefix, re.I)
        if inner:
            return _normalize_entity(inner.group(1)), _normalize_entity(inner.group(2))
    return None, None


def _normalize_entity(name: str) -> str:
    return re.sub(r"['']s$", "", name.strip())


def _entity_tokens(entity: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", entity.lower())
    return {word for word in words if word not in _ENTITY_STOP and len(word) > 2}


def _claim_references_entity(claim: str, entity: str) -> bool:
    tokens = _entity_tokens(entity)
    if not tokens:
        return False
    claim_lower = claim.lower()
    hits = sum(1 for token in tokens if token in claim_lower)
    return hits >= min(2, len(tokens))


def _filing_years_in_text(text: str) -> set[str]:
    years: set[str] = set()
    for match in _FILING_ANCHOR.finditer(text):
        year = match.group(1)
        if year:
            years.add(year)
    return years


def is_cross_filing_claim(
    claim: str,
    *,
    entity_a: str | None = None,
    entity_b: str | None = None,
) -> bool:
    """True when a claim synthesizes or compares both filings (natural language)."""
    lower = claim.lower()
    if len(_filing_years_in_text(claim)) >= 2:
        return True
    if entity_a and entity_b:
        if _claim_references_entity(claim, entity_a) and _claim_references_entity(claim, entity_b):
            return True
    if re.search(r"\bboth\b", lower):
        if re.search(r"\b(companies?|filings?|issuers?|counterpart|peers?)\b", lower):
            return True
        if entity_a and entity_b and _CROSS_VERB.search(claim):
            if _claim_references_entity(claim, entity_a) or _claim_references_entity(claim, entity_b):
                return True
    return bool(_CROSS_VERB.search(claim))


def per_filing_sides_covered(
    claims: list[str],
    *,
    entity_a: str | None = None,
    entity_b: str | None = None,
) -> int:
    """Count how many compared filings have at least one dedicated (non-cross) claim."""
    sides = 0
    if entity_a and entity_b:
        for claim in claims:
            if is_cross_filing_claim(claim, entity_a=entity_a, entity_b=entity_b):
                continue
            refs_a = _claim_references_entity(claim, entity_a)
            refs_b = _claim_references_entity(claim, entity_b)
            if refs_a and not refs_b:
                sides += 1
                break
        for claim in claims:
            if is_cross_filing_claim(claim, entity_a=entity_a, entity_b=entity_b):
                continue
            refs_a = _claim_references_entity(claim, entity_a)
            refs_b = _claim_references_entity(claim, entity_b)
            if refs_b and not refs_a:
                sides += 1
                break
        return sides
    anchored = [claim for claim in claims if _FILING_ANCHOR.search(claim)]
    return min(2, len(anchored))


def comparison_claims_are_structured(
    claims: list[str],
    *,
    answer: str,
    accessions: list[str] | None = None,
) -> bool:
    """Return True when claims support per-filing + cross-filing judge scoring."""
    _ = accessions  # reserved for accession-token matching in future
    normalized = [claim.strip() for claim in claims if claim and claim.strip()]
    if len(normalized) < 3 or len(normalized) > 8:
        return False
    entity_a, entity_b = extract_comparison_entities(answer)
    if per_filing_sides_covered(normalized, entity_a=entity_a, entity_b=entity_b) < 2:
        return False
    if not any(is_cross_filing_claim(claim, entity_a=entity_a, entity_b=entity_b) for claim in normalized):
        return False
    return True


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
    claims = [claim.strip() for claim in (gt.required_claims or []) if claim and claim.strip()]
    if not comparison_claims_are_structured(claims, answer=answer, accessions=accs):
        errors.append("required_claims")
    return errors


def derive_comparison_claims(answer: str, *, label_a: str, label_b: str, topic: str, section: str) -> list[str]:
    """Build minimum claim set when the model omits structured required_claims."""
    section_text = section.strip() or "the cited sections"
    cross = answer.strip() if _BOTH_FILINGS_PATTERN.search(answer) else (
        f"Both {label_a} and {label_b} compare how {topic} is addressed in {section_text}."
    )
    return [
        f"{label_a} discusses {topic} in {section_text}.",
        f"{label_b} discusses {topic} in {section_text}.",
        cross,
    ]
