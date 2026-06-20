"""Integration smoke for v2 publish sign-off gates (017)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evaluation.generation.bundle import publish_draft
from evaluation.generation.publish_audit import write_publish_audit
from models.benchmark_generation import (
    CorpusBundle,
    DatasetManifest,
    DatasetStatus,
    GenerationReport,
)

_COMPARISON_ANSWER = (
    "Both FY2025 and FY2024 10-K filings frame revenue differently: FY2025 emphasizes "
    "Services growth whereas FY2024 stresses iPhone cyclicality in Item 7 MD&A."
)
_COMPARISON_CLAIMS = [
    "FY2025 10-K discusses revenue in Item 7 MD&A.",
    "FY2024 10-K discusses revenue in Item 7 MD&A.",
    "Both filings contrast Services growth versus iPhone cyclicality.",
]


def _write_min_v2_draft(draft: Path, *, item_count: int = 200, multi_filing: int = 40) -> None:
    draft.mkdir(parents=True)
    manifest = DatasetManifest(
        schema_version="2.0.0",
        version="2.0.0",
        status=DatasetStatus.DRAFT,
        item_count=item_count,
        items_hash="sha256:test",
        sampling_manifest_path="sampling_manifest.json",
        generation_config_path="generation_config.yaml",
        corpus_bundle=CorpusBundle(
            snapshot_id="snap",
            issuer_snapshots=[],
            corpus_root="corpus",
            graph_node_index_path="corpus/graph_node_index.json",
            total_bytes=0,
        ),
        generation_judge_version="gemini",
        evaluation_judge_version="gemini",
        profile_counts={"financebench": item_count},
    )
    (draft / "manifest.json").write_text(manifest.model_dump_json(), encoding="utf-8")
    report = GenerationReport(
        run_id="smoke",
        candidates_total=item_count,
        accepted_count=item_count,
        rejected_count=0,
        pass_rate=1.0,
        judge_api_calls=0,
        storage_bytes_used=0,
        duration_seconds=1.0,
    )
    (draft / "generation_report.json").write_text(report.model_dump_json(), encoding="utf-8")
    (draft / "corpus").mkdir()
    (draft / "corpus" / "graph_node_index.json").write_text(
        json.dumps({"paths": ["0000320193-24-000123/item_7"]}),
        encoding="utf-8",
    )
    (draft / "reachability_report.json").write_text(
        json.dumps({"unreachable_answer_gt_count": 0}),
        encoding="utf-8",
    )
    items = []
    for i in range(item_count):
        multi = i < multi_filing
        items.append(
            {
                "item_id": f"v2-fin-{i:03d}",
                "question": "What is revenue?",
                "question_type_tag": "cross-filing-comparison" if multi else "metrics-generated",
                "answer_type": "comparison_structured" if multi else "numeric",
                "inspiration_profile": "financebench",
                "ground_truth": {
                    "answer": "42" if not multi else _COMPARISON_ANSWER,
                    "required_claims": (_COMPARISON_CLAIMS if multi else None),
                },
                "expected_bindings": {
                    "accessions": (
                        ["0000320193-25-000079", "0000320193-24-000123"]
                        if multi
                        else ["0000320193-24-000123"]
                    ),
                },
                "expected_section_paths": ["0000320193-24-000123/item_7"],
                "multi_filing_required": multi,
                "operation_class": "QUALITATIVE",
                "validation_status": "accepted",
            }
        )
    items_path = draft / "items" / "dev.jsonl"
    items_path.parent.mkdir(parents=True)
    items_path.write_text("\n".join(json.dumps(row) for row in items) + "\n", encoding="utf-8")
    from evaluation.generation.bundle import build_scorability_report, validate_bundle_feasibility

    feasibility = validate_bundle_feasibility(draft, items_path, manifest=manifest)
    (draft / "feasibility_report.json").write_text(json.dumps(feasibility), encoding="utf-8")
    (draft / "scorability_report.json").write_text(
        json.dumps(build_scorability_report(
            [__import__("models.benchmark_generation", fromlist=["GeneratedBenchmarkItem"]).GeneratedBenchmarkItem.model_validate(row) for row in items]
        )),
        encoding="utf-8",
    )


def test_v2_publish_blocked_without_audit(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    _write_min_v2_draft(draft)
    published = tmp_path / "published"
    with pytest.raises(ValueError, match="publish_audit"):
        publish_draft(
            draft,
            version="2.0.0",
            published_root=published,
            multi_filing_min=40,
            require_publish_audit=True,
        )


def test_v2_publish_selects_balanced_subset_from_pool(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    quotas = {"financebench": 0.34, "finder": 0.33, "finagentbench": 0.33}
    _write_min_v2_draft(draft, item_count=68, multi_filing=20)
    (draft / "generation_config.yaml").write_text(
        "bundle_schema_version: '2.0.0'\n"
        "random_seed: 20260602\n"
        f"profile_quotas: {json.dumps(quotas)}\n",
        encoding="utf-8",
    )
    pool_rows = []
    for profile, count in [("financebench", 80), ("finder", 75), ("finagentbench", 70)]:
        for index in range(count):
            multi = profile == "finagentbench"
            pool_rows.append(
                {
                    "item_id": f"v2-{profile}-{index:03d}",
                    "question": "What is revenue?",
                    "question_type_tag": "cross-filing-comparison" if multi else "metrics-generated",
                    "answer_type": "comparison_structured" if multi else "numeric",
                    "inspiration_profile": profile,
                    "ground_truth": {
                        "answer": "42" if not multi else _COMPARISON_ANSWER,
                        "required_claims": (_COMPARISON_CLAIMS if multi else None),
                    },
                    "expected_bindings": {
                        "accessions": (
                            ["0000320193-25-000079", "0000320193-24-000123"]
                            if multi
                            else ["0000320193-24-000123"]
                        ),
                    },
                    "expected_section_paths": ["0000320193-24-000123/item_7"],
                    "multi_filing_required": multi,
                    "operation_class": "QUALITATIVE",
                    "validation_status": "accepted",
                }
            )
    pool_path = draft / "items" / "dev_pool.jsonl"
    pool_path.write_text("\n".join(json.dumps(row) for row in pool_rows) + "\n", encoding="utf-8")
    write_publish_audit(
        draft,
        operator_id="tester",
        audit_item_ids=[pool_rows[0]["item_id"], pool_rows[70]["item_id"]],
    )
    published = tmp_path / "published"
    dest = publish_draft(
        draft,
        version="2.0.0",
        published_root=published,
        multi_filing_min=40,
        require_publish_audit=True,
        profile_quotas=quotas,
        selection_seed=20260602,
    )
    dev_lines = [
        json.loads(line)
        for line in (dest / "items" / "dev.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(dev_lines) == 200
    counts: dict[str, int] = {}
    for row in dev_lines:
        profile = row["inspiration_profile"]
        counts[profile] = counts.get(profile, 0) + 1
    assert counts["financebench"] == 68
    assert counts["finder"] == 66
    assert counts["finagentbench"] == 66
    manifest = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["item_count"] == 200
    assert manifest["profile_counts"]["finagentbench"] == 66


def test_v2_publish_with_signoff(tmp_path: Path) -> None:
    draft = tmp_path / "draft"
    _write_min_v2_draft(draft)
    write_publish_audit(
        draft,
        operator_id="tester",
        audit_item_ids=[f"v2-fin-{i:03d}" for i in range(20)],
    )
    published = tmp_path / "published"
    dest = publish_draft(
        draft,
        version="2.0.0",
        published_root=published,
        multi_filing_min=40,
        require_publish_audit=True,
        skip_gates=False,
    )
    assert (dest / "publish_audit.json").is_file()
