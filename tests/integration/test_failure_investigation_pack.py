"""Integration tests for failure investigation pack export (019)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from evaluation.reproduction.investigation.pack import export_failure_investigation_pack


def _fixture_draft(tmp_path: Path) -> Path:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    (draft / "corpus" / "graphs" / "AAPL").mkdir(parents=True)
    fixture_manifest = Path("tests/fixtures/custom_judge/corpus/graphs/AAPL/ci-aapl-snapshot.manifest.json")
    (draft / "corpus" / "graphs" / "AAPL" / "ci-aapl-snapshot.manifest.json").write_text(
        fixture_manifest.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    item = {
        "item_id": "v2-financebench-0001",
        "question": "What was revenue?",
        "question_type_tag": "single-fact",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "$416.16 billion", "answer_type": "numeric"},
        "expected_bindings": {"accessions": ["0000320193-24-000123"]},
        "expected_section_paths": ["0000320193-24-000123/XBRL"],
        "validation_status": "accepted",
    }
    (draft / "items" / "dev.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")
    return draft


def test_export_investigation_pack_csv_html_parity(tmp_path: Path) -> None:
    draft = _fixture_draft(tmp_path)
    repro = tmp_path / "repro"
    (repro / "graph-full").mkdir(parents=True)
    row = {
        "item_id": "v2-financebench-0001",
        "outcome_score": 0.0,
        "judge_status": "ok",
        "ranking_metrics": {"mrr": 1.0, "ndcg_at_10": 1.0},
        "answer": {
            "text": "Based on 2 evidence chunk(s) from SEC filings:",
            "citations": [
                {
                    "chunk_node_id": "c1",
                    "excerpt": "Revenue",
                    "content_hash": "h",
                    "accession": "0000320193-24-000123",
                    "section_id": "XBRL",
                }
            ],
        },
        "trajectory_snapshot": {"synthesis_path": "template"},
        "judge_verdict": {
            "judge_model": "test",
            "judge_version": "v1",
            "scores": {"value_alignment": 0.0},
        },
    }
    (repro / "graph-full" / "results.json").write_text(json.dumps([row]), encoding="utf-8")

    out = tmp_path / "investigation"
    html_path, csv_path = export_failure_investigation_pack(
        draft,
        out,
        repro_input=repro,
        item_ids=["v2-financebench-0001"],
    )
    assert html_path.is_file()
    assert csv_path.is_file()
    html = html_path.read_text(encoding="utf-8")
    assert "v2-financebench-0001" in html
    assert "synthesis_template_dump" in html or "Suggested failure" in html
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 1
    assert rows[0]["item_id"] == "v2-financebench-0001"
    assert "mrr" in rows[0]
