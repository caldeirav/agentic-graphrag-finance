"""Unit tests for review pack export (018)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.generation.review.review_pack import (
    build_review_pack_rows,
    render_review_pack_html,
    write_review_pack_csv,
)


def _draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    rows = [
        {
            "item_id": "v2-financebench-0001",
            "question": "Compare risks?",
            "question_type_tag": "cross-filing-comparison",
            "inspiration_profile": "finagentbench",
            "ground_truth": {"answer": "Substantive answer.", "required_claims": ["a", "b", "c"]},
            "expected_bindings": {"accessions": ["acc-a", "acc-b"]},
            "expected_section_paths": ["acc-a/Item1A", "acc-b/Item1A"],
            "validation_status": "accepted",
        },
        {
            "item_id": "v2-financebench-0002",
            "question": "Other?",
            "question_type_tag": "cross-filing-comparison",
            "inspiration_profile": "finagentbench",
            "ground_truth": {"answer": "Other answer."},
            "expected_bindings": {"accessions": ["acc-a", "acc-b"]},
            "expected_section_paths": ["acc-a/Item7"],
            "validation_status": "accepted",
        },
    ]
    (draft / "items" / "dev.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n",
        encoding="utf-8",
    )
    return draft


def test_review_pack_row_parity(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    ids = ["v2-financebench-0001", "v2-financebench-0002"]
    rows = build_review_pack_rows(draft, ids)
    assert len(rows) == 2
    assert rows[0]["item_id"] == ids[0]
    assert "canonical_answer" in rows[0]
    assert "section_paths" in rows[0]


def test_csv_html_row_count_match(tmp_path: Path) -> None:
    draft = _draft(tmp_path)
    ids = ["v2-financebench-0001"]
    rows = build_review_pack_rows(draft, ids)
    csv_path = write_review_pack_csv(rows, tmp_path / "pack.csv")
    html = render_review_pack_html(rows)
    assert csv_path.read_text(encoding="utf-8").count("v2-financebench-0001") >= 1
    assert html.count("v2-financebench-0001") == 1
    assert "Compare risks?" in html
