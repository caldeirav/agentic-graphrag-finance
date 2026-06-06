"""Unit tests for aggregated investigation notes (015)."""

from datetime import UTC, datetime

from evaluation.reproduction.report_models import ItemResultRecord, ReproOutputBundle, TableData
from evaluation.reproduction.report_render import MAX_INVESTIGATION_NOTES, aggregate_investigation_notes
from models.reproduction import EvalRunRef, ReproRun


def _bundle_with_zero_cite_ablation(variant: str, count: int) -> ReproOutputBundle:
    records = [
        ItemResultRecord(
            variant_id=variant,
            item_id=f"item-{i}",
            judge_status="ok",
            citation_count=0,
            outcome_score=0.0,
            source_path="",
        )
        for i in range(count)
    ]
    return ReproOutputBundle(
        output_dir=__import__("pathlib").Path("/tmp"),
        repro_run=ReproRun(
            repro_run_id="r",
            release_tag="paper-v1.0",
            manifest_hash="h",
            variant_runs=[EvalRunRef(variant_id=variant, report_dir=".")],
        ),
        tables={
            "headline": TableData(
                columns=["variant_id", "metric_name", "value", "item_count"],
                rows=[
                    {
                        "variant_id": variant,
                        "metric_name": "mrr",
                        "value": "0.0",
                        "item_count": str(count),
                    }
                ],
            )
        },
        variant_results={variant: records},
    )


def test_ablation_zero_citations_aggregated_once() -> None:
    bundle = _bundle_with_zero_cite_ablation("ablation-no-walker", 50)
    notes = aggregate_investigation_notes(bundle)
    ablation_notes = [n for n in notes if n.pattern_code == "ABLATION_ZERO_CITATIONS"]
    assert len(ablation_notes) == 1
    assert ablation_notes[0].item_count == 50
    assert len(ablation_notes[0].example_item_ids) <= 5


def test_investigation_notes_capped() -> None:
    variants = {f"variant-{i}": [] for i in range(40)}
    records_map = {}
    for vid in variants:
        records_map[vid] = [
            ItemResultRecord(
                variant_id=vid,
                item_id=f"{vid}-x",
                judge_status="ok",
                citation_count=0,
                source_path="",
            )
        ]
    bundle = ReproOutputBundle(
        output_dir=__import__("pathlib").Path("/tmp"),
        repro_run=ReproRun(repro_run_id="r", release_tag="t", manifest_hash="h"),
        tables={"headline": TableData(columns=[], rows=[])},
        variant_results=records_map,
    )
    notes = aggregate_investigation_notes(bundle)
    assert len(notes) <= MAX_INVESTIGATION_NOTES
