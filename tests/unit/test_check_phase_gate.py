"""Unit tests for 022 phase gate evaluation."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.investigation.phase_gate import evaluate_phase_gate

_TARGETS = (
    Path(__file__).resolve().parents[2]
    / "specs/022-outcome-score-ladder/fixtures/cohort_phase_targets.json"
)


def _write_results(report: Path, rows: list[dict]) -> None:
    out = report / "graph-full"
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps(rows), encoding="utf-8")


def test_phase_a_fails_on_forbidden_dollar_rate(tmp_path: Path) -> None:
    cohort = tmp_path / "cohort.json"
    cohort.write_text(json.dumps({"item_ids": ["v2-financebench-0548", "v2-financebench-0667"]}))

    report = tmp_path / "report"
    _write_results(
        report,
        [
            {
                "item_id": "v2-financebench-0548",
                "outcome_score": 0.5,
                "answer": {"text": "The net profit margin was $8.67 billion.", "citations": []},
            },
            {
                "item_id": "v2-financebench-0667",
                "outcome_score": 0.0,
                "answer": {"text": "Cannot determine effective tax rate.", "citations": []},
            },
        ],
    )

    targets = tmp_path / "targets.json"
    targets.write_text(
        json.dumps(
            {
                "phase_a_ratio": {
                    "primary_item_ids": ["v2-financebench-0548"],
                    "gate_outcome_gt0_floor": 1,
                    "forbidden_answer_patterns": ["margin.*was \\$"],
                }
            }
        ),
        encoding="utf-8",
    )

    result = evaluate_phase_gate(
        report_dir=report,
        phase="A",
        cohort_path=cohort,
        targets_path=targets,
    )
    assert result["outcome_gt0"] == 1
    assert result["forbidden_pattern_hits"] >= 1
    assert result["passed"] is False


def test_phase_a_passes_with_percent_answers(tmp_path: Path) -> None:
    cohort = tmp_path / "cohort.json"
    item_ids = [f"v2-financebench-{i:04d}" for i in range(4)]
    cohort.write_text(json.dumps({"item_ids": item_ids}), encoding="utf-8")

    report = tmp_path / "report"
    rows = [
        {
            "item_id": item_ids[0],
            "outcome_score": 1.0,
            "answer": {"text": "Net profit margin was 12.3%.", "citations": []},
        },
        {
            "item_id": item_ids[1],
            "outcome_score": 0.5,
            "answer": {"text": "Effective tax rate was 21.1%.", "citations": []},
        },
    ] + [
        {
            "item_id": iid,
            "outcome_score": 0.0,
            "answer": {"text": "Cannot determine.", "citations": []},
        }
        for iid in item_ids[2:]
    ]
    _write_results(report, rows)

    result = evaluate_phase_gate(
        report_dir=report,
        phase="A",
        cohort_path=cohort,
        targets_path=_TARGETS,
    )
    assert result["outcome_gt0"] == 2
    assert result["forbidden_pattern_hits"] == 0
    assert result["passed"] is True
