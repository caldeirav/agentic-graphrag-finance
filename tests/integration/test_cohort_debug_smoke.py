"""Integration tests for cohort debug replay mode (019)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.investigation.cohort import Tier1CohortFile
from evaluation.reproduction.investigation.cohort_debug import run_cohort_debug_replay


def test_cohort_debug_replay_writes_summaries(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    (draft / "items").mkdir(parents=True)
    item = {
        "item_id": "v2-test-debug-1",
        "question": "Q",
        "question_type_tag": "single-fact",
        "inspiration_profile": "financebench",
        "ground_truth": {"answer": "1"},
        "expected_bindings": {"accessions": ["acc-a"]},
        "expected_section_paths": ["acc-a/XBRL"],
        "validation_status": "accepted",
    }
    (draft / "items" / "dev.jsonl").write_text(json.dumps(item) + "\n", encoding="utf-8")

    repro = tmp_path / "repro"
    (repro / "graph-full").mkdir(parents=True)
    result = {
        "item_id": "v2-test-debug-1",
        "outcome_score": 0.0,
        "answer": {"text": "answer", "citations": []},
        "trajectory_snapshot": {"synthesis_path": "live_llm", "document_route": [{"accession": "acc-a"}]},
        "judge_verdict": {
            "judge_model": "test",
            "judge_version": "v1",
            "scores": {"value_alignment": 0.0, "retrieval_fidelity": 0.5},
        },
    }
    (repro / "graph-full" / "results.json").write_text(json.dumps([result]), encoding="utf-8")

    cohort_path = tmp_path / "cohort.json"
    cohort = Tier1CohortFile(
        source_queue_path=str(cohort_path),
        source_queue_hash="abc",
        item_ids=["v2-test-debug-1"],
    )
    cohort_path.write_text(cohort.model_dump_json(), encoding="utf-8")

    out = tmp_path / "debug-out"
    summaries = run_cohort_debug_replay(
        draft=draft,
        replay_input=repro,
        cohort_path=cohort_path,
        output_dir=out,
        resume=False,
    )
    assert len(summaries) == 1
    summary_path = out / "cohort_debug" / "v2-test-debug-1.summary.json"
    assert summary_path.is_file()
    payload = json.loads(summary_path.read_text(encoding="utf-8"))
    assert payload["item_id"] == "v2-test-debug-1"
    assert payload["synthesis_path"] == "live_llm"
