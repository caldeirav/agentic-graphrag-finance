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
    r"\b(compare|comparison|contrast|compared|versus|vs\.?|whereas|while|"
    r"similar|differ|difference|differently|shared|common|in common|relative to|"
    r"emphasiz\w+)\b",
    re.IGNORECASE,
)
_BOTH_AND_PATTERN = re.compile(r"both\s+.+\s+and\s+.+", re.IGNORECASE)


def is_comparison_canonical_answer(answer: str) -> bool:
    """True when answer names both filings in a comparison-structured canonical form."""
    text = (answer or "").strip()
    if not text:
        return False
    if _BOTH_FILINGS_PATTERN.search(text):
        return True
    return bool(_BOTH_AND_PATTERN.search(text) and _CROSS_VERB.search(text))


COMPARISON_ANSWER_PROMPT_RULES = """\
Comparison canonical answer rules (finagentbench / comparison_structured):
- ground_truth.answer MUST open with "Both {filing A} and {filing B} ..." naming both compared filings.
- The answer MUST state a compared conclusion (difference, similarity, or relative emphasis).
- Valid opening patterns include:
  * "Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K discuss {topic} differently: ..."
  * "Both Caterpillar and Exxon Mobil emphasize different risks, with Caterpillar ... whereas Exxon ..."
- Use contrast language: whereas, while, emphasizes, differs, contrasts, relative to.
- Do NOT only state that both filings mention a topic in a section (boilerplate).
- required_claims: 3-8 claims with per-filing (A only, B only) + at least one cross-filing synthesis claim.
"""

_COMPARISON_ERROR_CODES = frozenset(
    {
        "invalid_answer_type",
        "boilerplate_comparison_answer",
        "required_claims",
        "comparison_bindings",
        "missing_answer_gt",
    }
)

_VALIDATION_FEEDBACK_HINTS: dict[str, str] = {
    "invalid_answer_type": (
        "ground_truth.answer must use 'Both {A} and {B} ...' with a compared conclusion "
        "(discuss/address OR emphasize/whereas/differs/contrast)."
    ),
    "boilerplate_comparison_answer": (
        "Answer only states section co-occurrence. Add an explicit compared conclusion "
        "(difference, similarity, or relative emphasis) using whereas/while/emphasizes/differs."
    ),
    "required_claims": (
        "required_claims must include: (1) claim for filing A only, (2) claim for filing B only, "
        "(3) at least one cross-filing synthesis claim comparing both on the topic."
    ),
    "comparison_bindings": "expected_bindings.accessions must include >=2 distinct accessions.",
    "missing_answer_gt": "ground_truth.answer is required and must be non-empty.",
    "finagentbench_requires_multi_filing": (
        "finagentbench items require >=2 accessions and multi_filing_required=true."
    ),
    "unknown_section_path": (
        "Copy expected_section_paths exactly from available_section_paths (section slugs only)."
    ),
}


def format_generation_validation_feedback(
    feedback: str | list[str] | None,
    *,
    profile: str = "",
) -> str:
    """Turn validator error codes into actionable Gemini retry guidance."""
    if not feedback:
        return ""
    if isinstance(feedback, str):
        codes = [part.strip() for part in feedback.split(";") if part.strip()]
    else:
        codes = [str(part).strip() for part in feedback if str(part).strip()]
    if not codes:
        return ""

    lines = ["Previous attempt failed validation:"]
    seen_hints: set[str] = set()
    comparison_related = profile == "finagentbench"
    for code in codes:
        base = code.split(":", 1)[0]
        if base in _COMPARISON_ERROR_CODES:
            comparison_related = True
        hint = _VALIDATION_FEEDBACK_HINTS.get(base)
        if hint and hint not in seen_hints:
            lines.append(f"- {base}: {hint}")
            seen_hints.add(hint)
        elif base.startswith("unknown_section_path"):
            key = "unknown_section_path"
            if key not in seen_hints:
                lines.append(f"- {key}: {_VALIDATION_FEEDBACK_HINTS[key]}")
                seen_hints.add(key)
        elif base not in _VALIDATION_FEEDBACK_HINTS:
            lines.append(f"- {code}")

    if comparison_related:
        lines.append(COMPARISON_ANSWER_PROMPT_RULES)
    lines.append("Fix the JSON so all section paths exist in available_section_paths.")
    return "\n".join(lines) + "\n"


_PERCENT = re.compile(r"\d+\.?\d*%")
_DOLLAR = re.compile(r"\$[\d,]+(?:\.\d+)?")
_TEMPLATE_STRIP = re.compile(
    r"\b(?:both|and|discuss|address|describe|mention|cover|in|item|risk|factors|"
    r"management|discussion|10-k|10-q|fy20\d{2})\b",
    re.IGNORECASE,
)


def _normalized_word_count(answer: str) -> int:
    tokens = [t for t in _TEMPLATE_STRIP.sub(" ", answer.lower()).split() if t]
    return len(tokens)


def _has_numeric_contrast(answer: str) -> bool:
    pcts = _PERCENT.findall(answer)
    dollars = _DOLLAR.findall(answer)
    return len(set(pcts)) >= 2 or len(set(dollars)) >= 2


def is_boilerplate_comparison_answer(answer: str) -> bool:
    """True when canonical comparison answer is section co-occurrence only (018)."""
    text = (answer or "").strip()
    if not text:
        return False
    if not _BOTH_FILINGS_PATTERN.search(text):
        return False
    if _CROSS_VERB.search(text):
        return False
    if _normalized_word_count(text) >= 25:
        return False
    if _has_numeric_contrast(text):
        return False
    return True


def comparison_answer_informativeness_score(answer: str) -> float:
    text = (answer or "").strip()
    if not text or is_boilerplate_comparison_answer(text):
        return 0.0
    score = 0.2 if _BOTH_FILINGS_PATTERN.search(text) else 0.4
    if _CROSS_VERB.search(text):
        score += 0.4
    words = len(text.split())
    if words >= 25:
        score += 0.2
    if _has_numeric_contrast(text):
        score += 0.2
    return min(1.0, score)


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
        inner = re.match(
            r"both\s+(.+?)\s+and\s+(.+?)\s+(?:discuss|address|describe|mention|cover)",
            prefix,
            re.I,
        )
        if inner:
            return _normalize_entity(inner.group(1)), _normalize_entity(inner.group(2))
    match = re.search(
        r"both\s+([^,]+?)\s+and\s+([^,]+?)\s+"
        r"(?:emphasiz\w*|contrast(?:s|ed|ing)?|differ(?:s|ent|ently)?|compare[ds]?|"
        r"frame[ds]?|highlight(?:s|ed|ing)?|whereas|while)\b",
        text,
        re.IGNORECASE,
    )
    if match:
        return _normalize_entity(match.group(1)), _normalize_entity(match.group(2))
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
    if not is_comparison_canonical_answer(answer):
        errors.append("invalid_answer_type")
    if is_boilerplate_comparison_answer(answer):
        errors.append("boilerplate_comparison_answer")
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
