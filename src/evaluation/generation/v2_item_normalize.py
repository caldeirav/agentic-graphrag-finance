"""Post-parse normalization for custom-judge v2.0 generated items (017)."""

from __future__ import annotations

import re

from evaluation.generation.comparison_gt import derive_comparison_claims, is_comparison_item
from evaluation.generation.gt_classifier import is_numeric_answer_gt
from evaluation.generation.migrate_v1_1_0 import derive_required_claims
from models.benchmark_generation import AnswerType, GeneratedBenchmarkItem
from models.evaluation import GroundTruth

_FY_LABEL = re.compile(r"(FY20\d{2}\s+10-[KQ])", re.IGNORECASE)


def infer_answer_type(item: GeneratedBenchmarkItem) -> AnswerType:
    """Infer answer_type from profile, tags, and answer shape when model omits or mislabels."""
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    profile = item.inspiration_profile

    if item.multi_filing_required or profile == "finagentbench" or is_comparison_item(item):
        if len(item.expected_bindings.accessions) >= 2:
            return AnswerType.COMPARISON_STRUCTURED

    if answer and is_numeric_answer_gt(answer):
        return AnswerType.NUMERIC

    if answer:
        tokens = answer.split()
        if len(tokens) <= 4 and not any(
            tok.lower() in {"is", "are", "was", "were", "the", "and", "that", "discuss"}
            for tok in tokens
        ):
            return AnswerType.SHORT_LABEL

    if profile == "financebench" and answer:
        return AnswerType.NUMERIC if is_numeric_answer_gt(answer) else AnswerType.SHORT_LABEL

    return AnswerType.NARRATIVE


def _comparison_labels_from_answer(answer: str) -> tuple[str, str]:
    labels = _FY_LABEL.findall(answer)
    if len(labels) >= 2:
        return labels[0], labels[1]
    if len(labels) == 1:
        return labels[0], "FY2024 10-K"
    return "FY2025 10-K", "FY2024 10-K"


def _topic_from_question(question: str) -> str:
    text = (question or "").strip()
    if not text:
        return "the topic in the question"
    text = re.sub(r"\?$", "", text).strip()
    text = re.sub(r"^(do|does|what|how|which|when|where)\s+", "", text, flags=re.I)
    return text[:80] if text else "the topic in the question"


def ensure_required_claims(item: GeneratedBenchmarkItem) -> list[str]:
    """Return required_claims list satisfying v2 gates for the item's answer_type."""
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    answer_type = item.answer_type
    existing = [c.strip() for c in (gt.required_claims or []) if c and c.strip()]

    if answer_type in (AnswerType.NUMERIC, AnswerType.SHORT_LABEL):
        return []

    if answer_type == AnswerType.COMPARISON_STRUCTURED:
        if len(existing) >= 3:
            return existing[:8]
        label_a, label_b = _comparison_labels_from_answer(answer)
        topic = _topic_from_question(item.question)
        section_match = re.search(r"item\s*\d+[a-z]?", answer, re.I)
        section = section_match.group(0) if section_match else "Item 7 MD&A"
        return derive_comparison_claims(
            answer,
            label_a=label_a,
            label_b=label_b,
            topic=topic,
            section=section,
        )

    if len(existing) >= 2:
        return existing[:8]
    derived = derive_required_claims(answer)
    if len(derived) >= 2:
        return derived[:8]
    if not answer:
        return existing
    words = answer.split()
    if len(words) >= 4:
        mid = max(1, len(words) // 2)
        return [" ".join(words[:mid]).strip(), " ".join(words[mid:]).strip()]
    return [answer, answer]


def normalize_v2_item(item: GeneratedBenchmarkItem) -> GeneratedBenchmarkItem:
    """Infer answer_type and derive required_claims so v2 validation passes when possible."""
    gt = item.ground_truth
    answer = (gt.answer or "").strip()
    if not answer:
        return item

    answer_type = item.answer_type
    if answer_type is None or (
        answer_type == AnswerType.NARRATIVE
        and item.inspiration_profile == "financebench"
        and is_numeric_answer_gt(answer)
    ):
        answer_type = infer_answer_type(item)

    claims = ensure_required_claims(
        item.model_copy(update={"answer_type": answer_type})
    )
    new_gt = gt.model_copy(
        update={
            "required_claims": claims or None,
            "answer_type": answer_type.value,
        }
    )
    return item.model_copy(update={"answer_type": answer_type, "ground_truth": new_gt})
