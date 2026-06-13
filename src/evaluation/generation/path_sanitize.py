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
_QUARTER_YEAR = re.compile(
    r"\b(?:q(?P<q>[1-4])|(?P<word>first|second|third|fourth)\s+quarter)\s+(?:of\s+)?(?P<year>20\d{2})\b",
    re.I,
)
_YEAR_ONLY = re.compile(r"\b(20\d{2})\b")

_DIVESTITURE_TERMS = (
    "divest",
    "asset sale",
    "proceeds from sale",
    "proceeds from asset",
    "singapore retail",
    "mobil argentina",
    "$1.1 billion",
    "1.1 billion",
    "1100000000",
)


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


def is_divestiture_item(
    question: str,
    *,
    answer: str = "",
    gt_text: str = "",
) -> bool:
    combined = f"{question} {answer} {gt_text}".lower()
    return any(term in combined for term in _DIVESTITURE_TERMS)


def quarter_year_from_question(question: str) -> tuple[int | None, int | None]:
    """Return (quarter 1-4, year) when the question cites a fiscal quarter."""
    q = question or ""
    match = _QUARTER_YEAR.search(q)
    if match:
        if match.group("q"):
            quarter = int(match.group("q"))
        else:
            word = (match.group("word") or "").lower()
            quarter = {"first": 1, "second": 2, "third": 3, "fourth": 4}[word]
        return quarter, int(match.group("year"))
    if re.search(r"\bq1\b", q, re.I):
        year_match = _YEAR_ONLY.search(q)
        return 1, int(year_match.group(1)) if year_match else None
    return None, None


def is_quarterly_divestiture_item(
    question: str,
    *,
    answer: str = "",
    gt_text: str = "",
) -> bool:
    if not is_divestiture_item(question, answer=answer, gt_text=gt_text):
        return False
    quarter, _year = quarter_year_from_question(question)
    q = question.lower()
    return quarter is not None or "q1" in q or "q2" in q or "q3" in q or "q4" in q or "quarter" in q


def path_tail_is_business_section(path: str) -> bool:
    _, tail = parse_section_path(path)
    tail_lower = tail.lower()
    return "item 1" in tail_lower and "business" in tail_lower


def path_tail_is_xbrl(path: str) -> bool:
    return "xbrl" in path.lower()


def path_tail_is_mda(path: str) -> bool:
    _, tail = parse_section_path(path)
    tail_lower = tail.lower()
    return any(
        token in tail_lower
        for token in (
            "management",
            "discussion",
            "md_and_a",
            "item 2",
            "item 7",
            "10-q",
        )
    )


def needs_v2_path_repair(row: dict) -> bool:
    """True when v1 repair mapped paths to the wrong narrative section."""
    paths = list(row.get("expected_section_paths") or [])
    if not paths:
        return False
    if any(is_corrupt_section_path(path) for path in paths):
        return True

    gt = row.get("ground_truth") or {}
    answer = str(gt.get("answer") or "")
    claims = " ".join(gt.get("required_claims") or [])
    question = row.get("question") or ""

    if is_divestiture_item(question, answer=answer, gt_text=claims):
        if all(path_tail_is_business_section(path) or path_tail_is_xbrl(path) for path in paths):
            return True

    profile = row.get("inspiration_profile", "")
    q_lower = question.lower()
    if profile == "finagentbench" and any(
        token in q_lower for token in ("segment", "revenue", "net sales", "md&a", "item 7")
    ):
        if all("1a" in path.lower() or "risk" in path.lower() for path in paths):
            return True

    return False


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

    if is_divestiture_item(question, answer=answer, gt_text=gt_text):
        if is_quarterly_divestiture_item(question, answer=answer, gt_text=gt_text):
            hints.extend(["10-q", "item 2", "management", "discussion", "md_and_a"])
        else:
            hints.extend(["item 7", "management", "discussion", "md_and_a", "mda"])
        hints.extend(["divest", "asset sale", "proceeds"])
    elif any(k in combined for k in ("risk factor", "item 1a", "item1a", "1a risk")):
        hints.extend(["risk", "item 1a", "item1a", "risk_factors"])
    if any(k in combined for k in ("md&a", "mda", "management's discussion", "item 7")):
        hints.extend(["mda", "management", "discussion", "item 7", "md_and_a", "item 2"])
    if any(k in combined for k in ("segment", "business unit", "product line", "geographic")):
        hints.extend(["segment", "business", "product", "geographic"])
    if any(k in combined for k in ("footnote", "note ", "notes to")):
        hints.extend(["note", "footnote"])
    if any(k in combined for k in ("officer", "executive", "director", "ceo", "cfo")):
        hints.extend(["executive", "officer", "director"])
    if (
        not is_divestiture_item(question, answer=answer, gt_text=gt_text)
        and any(
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
        )
        and not any(k in q for k in ("divest", "proceeds", "asset sale"))
    ):
        hints.extend(["xbrl", "financial facts"])
    if not hints:
        if "compare" in q or "comparison" in q:
            hints.extend(["item 7", "management", "mda"])
        else:
            hints.extend(["item 7", "management"])
    return hints


def pick_section_path_for_accession(
    accession: str,
    graph_paths: set[str],
    hints: list[str],
    *,
    question: str = "",
    answer: str = "",
    gt_text: str = "",
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

    divestiture = is_divestiture_item(question, answer=answer, gt_text=gt_text)
    quarter, year = quarter_year_from_question(question)

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

        if divestiture:
            if path_tail_is_business_section(path):
                score -= 25
            if path_tail_is_xbrl(path):
                score -= 20
            if "10-q" in tail_lower:
                score += 10
            if any(token in tail_lower for token in ("management", "discussion", "item 2", "item 7")):
                score += 8
            if year is not None and str(year) in tail_lower:
                score += 4
            if quarter == 1 and any(token in tail_lower for token in ("03-31", "03/31", "mar")):
                score += 3
            if quarter == 2 and any(token in tail_lower for token in ("06-30", "06/30", "jun")):
                score += 3

        scored.append((score, path))

    if not scored:
        return None
    best_score = max(s for s, _ in scored)
    if best_score <= 0:
        return None
    return sorted(p for s, p in scored if s == best_score)[0]
