"""Detect and repair corrupt expected_section_paths (sentence fragments vs section slugs)."""

from __future__ import annotations

import re

from evaluation.generation.section_paths import (
    item_number_key,
    normalize_section_key,
    parse_section_path,
)

_CORRUPT_TAIL = re.compile(
    r"[\$€£]|\b(billion|million|thousand|bn|mm)\b|\d{5,}",
    re.IGNORECASE,
)
_ITEM_REF = re.compile(r"\bitem\s*\d+[a-z]?\b", re.I)


def is_corrupt_section_path_tail(tail: str) -> bool:
    """True when tail looks like an answer fragment rather than a section slug."""
    text = (tail or "").strip()
    if not text:
        return True
    if _CORRUPT_TAIL.search(text):
        return True
    tk = normalize_section_key(text)
    if item_number_key(tk) or _ITEM_REF.search(text):
        return False
    if len(text) <= 48 and text.count(" ") <= 4:
        slugish = text.replace("_", " ").replace("-", " ")
        if slugish.count(" ") <= 3:
            return False
    if len(text) > 60 or text.count(" ") >= 6:
        return True
    if text[0].islower() and "item" not in text.lower()[:12]:
        return True
    return False


def is_corrupt_section_path(path: str) -> bool:
    _, tail = parse_section_path(path)
    return is_corrupt_section_path_tail(tail)


def filter_canonical_graph_paths(paths: set[str]) -> set[str]:
    """Drop sentence-fragment paths from graph_node_index exports."""
    return {p for p in paths if not is_corrupt_section_path(p)}


def infer_section_hints(
    question: str,
    *,
    answer: str = "",
    gt_text: str = "",
) -> list[str]:
    """Return lowercase substrings to match against graph index paths."""
    q = (question or "").lower()
    hints: list[str] = []
    combined = f"{q} {answer.lower()} {gt_text.lower()}"

    if any(k in combined for k in ("risk factor", "item 1a", "item1a", "1a risk")):
        hints.extend(["risk", "item 1a", "item1a", "risk_factors"])
    if any(k in combined for k in ("md&a", "mda", "management's discussion", "item 7")):
        hints.extend(["mda", "management", "discussion", "item 7", "md_and_a"])
    if any(k in combined for k in ("segment", "business unit", "product line", "geographic")):
        hints.extend(["segment", "business", "product", "geographic"])
    if any(k in combined for k in ("footnote", "note ", "notes to")):
        hints.extend(["note", "footnote"])
    if any(k in combined for k in ("officer", "executive", "director", "ceo", "cfo")):
        hints.extend(["executive", "officer", "director"])
    if any(
        k in q
        for k in (
            "revenue",
            "sales",
            "net income",
            "earnings",
            "assets",
            "eps",
            "year over year",
            "yoy",
            "quarter over quarter",
            "qoq",
        )
    ):
        hints.extend(["xbrl", "financial facts"])
    if not hints:
        if "compare" in q or "comparison" in q:
            hints.extend(["item 7", "management", "mda"])
        else:
            hints.extend(["item 7", "business"])
    return hints


def pick_section_path_for_accession(
    accession: str,
    graph_paths: set[str],
    hints: list[str],
) -> str | None:
    """Choose the best graph index path for one accession using hint substrings."""
    acc_compact = accession.replace("-", "")
    candidates = [
        p
        for p in graph_paths
        if accession in p or acc_compact in p.replace("-", "")
    ]
    if not candidates:
        return None

    scored: list[tuple[int, str]] = []
    for path in candidates:
        _, tail = parse_section_path(path)
        if is_corrupt_section_path_tail(tail):
            continue
        tail_lower = tail.lower()
        score = 0
        for hint in hints:
            if hint in tail_lower:
                score += 3
        if "xbrl" in tail_lower and any(h in hints for h in ("xbrl", "financial facts")):
            score += 5
        if item_number_key(normalize_section_key(tail)):
            score += 2
        scored.append((score, path))

    if not scored:
        return None
    best_score = max(s for s, _ in scored)
    if best_score <= 0:
        return None
    return sorted(p for s, p in scored if s == best_score)[0]
