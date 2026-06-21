"""Unit tests for cohort validation gate (019)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.investigation.cohort_gate import (
    build_cohort_validation_report,
    load_cohort_gate_thresholds,
)
from models.investigation import CohortValidationReport, Tier1CohortFile


def test_load_thresholds_from_manifest() -> None:
    manifest = {
        "cohort_gate_thresholds": {
            "max_strong_retrieval_zero_outcome": 50,
            "max_mrr_ok_va_zero": 8,
        }
    }
    thresholds = load_cohort_gate_thresholds(manifest)
    assert thresholds.max_strong_retrieval_zero_outcome == 50
    assert thresholds.max_mrr_ok_va_zero == 8


def test_cohort_report_fails_when_strong_zero_exceeds_threshold(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    item_row = {
        "item_id": "v2-test-0001",
        "question": "Q",
        "question_type_tag": "single-fact",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "1"},
        "expected_bindings": {"accessions": ["acc"]},
        "expected_section_paths": ["acc/XBRL"],
        "validation_status": "accepted",
    }
    (draft / "items" / "dev.jsonl").write_text(json.dumps(item_row) + "\n", encoding="utf-8")

    repro = tmp_path / "repro"
    (repro / "graph-full").mkdir(parents=True)
    result_row = {
        "item_id": "v2-test-0001",
        "outcome_score": 0.0,
        "judge_status": "ok",
        "ranking_metrics": {"mrr": 1.0, "ndcg_at_10": 1.0},
        "answer": {"text": "Based on 1 evidence chunk(s)", "citations": []},
        "trajectory_snapshot": {"synthesis_path": "template"},
    }
    (repro / "graph-full" / "results.json").write_text(
        json.dumps([result_row]) + "\n",
        encoding="utf-8",
    )

    cohort_path = tmp_path / "tier1_cohort.json"
    cohort = Tier1CohortFile(
        source_queue_path=str(cohort_path),
        source_queue_hash="abc",
        item_ids=["v2-test-0001"],
    )
    cohort_path.write_text(cohort.model_dump_json(), encoding="utf-8")

    manifest = {
        "release_tag": "paper-v1.1",
        "cohort_gate_thresholds": {
            "max_strong_retrieval_zero_outcome": 0,
            "max_mrr_ok_va_zero": 0,
            "require_regression_suite_pass": False,
        },
    }
    report = build_cohort_validation_report(
        cohort=cohort,
        cohort_path=cohort_path,
        output_dir=tmp_path / "validate",
        manifest=manifest,
        draft=draft,
        repro_input=repro,
        skip_regression_check=True,
    )
    assert report.passed is False
    assert report.strong_retrieval_zero_count == 1
    assert any("strong_retrieval_zero_outcome" in item for item in report.failed_thresholds)
