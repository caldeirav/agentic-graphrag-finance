"""Unit tests for evidence-source matrix and report section layout (014/016)."""

from __future__ import annotations

from pathlib import Path

from evaluation.reproduction.report_models import ReproOutputBundle, TableData
from evaluation.reproduction.report_render import (
    _render_drilldown_html,
    _render_outcome_by_profile_html,
    _render_outcome_by_stratum_html,
    _render_tables_html,
    aggregate_investigation_notes,
    build_paper_table_views,
    render_html_report,
)
from models.reproduction import EvalRunRef, ReproRun


def _bundle_with_tables(headline_rows: list[dict], extra_tables: dict[str, TableData]) -> ReproOutputBundle:
    tables = {
        "headline": TableData(
            columns=["variant_id", "metric_name", "value", "item_count"],
            rows=headline_rows,
        ),
        **extra_tables,
    }
    return ReproOutputBundle(
        output_dir=Path("/tmp"),
        repro_run=ReproRun(
            repro_run_id="r",
            release_tag="paper-v1.0",
            manifest_hash="h",
            variant_runs=[
                EvalRunRef(variant_id="graph-full", report_dir="."),
                EvalRunRef(variant_id="flat-chunk", report_dir="."),
            ],
        ),
        tables=tables,
        variant_results={},
    )


def test_outcome_by_profile_section_removed_from_html() -> None:
    bundle = _bundle_with_tables(
        [],
        {
            "by_profile": TableData(
                columns=[
                    "variant_id",
                    "inspiration_profile",
                    "metric_name",
                    "value",
                    "item_count",
                    "na_reason",
                ],
                rows=[
                    {
                        "variant_id": "graph-full",
                        "inspiration_profile": "financebench",
                        "metric_name": "outcome_accuracy",
                        "value": "0.80",
                        "item_count": "10",
                        "na_reason": "",
                    },
                ],
            )
        },
    )
    assert _render_outcome_by_profile_html(bundle) == ""


def test_evidence_source_section_pivots_all_metrics() -> None:
    bundle = _bundle_with_tables(
        [],
        {
            "by_evidence_source": TableData(
                columns=[
                    "variant_id",
                    "primary_evidence_source",
                    "metric_name",
                    "value",
                    "item_count",
                    "na_reason",
                ],
                rows=[
                    {
                        "variant_id": "graph-full",
                        "primary_evidence_source": "html",
                        "metric_name": "outcome_accuracy",
                        "value": "0.70",
                        "item_count": "8",
                        "na_reason": "",
                    },
                    {
                        "variant_id": "graph-full",
                        "primary_evidence_source": "html",
                        "metric_name": "mrr",
                        "value": "0.55",
                        "item_count": "8",
                        "na_reason": "",
                    },
                    {
                        "variant_id": "flat-chunk",
                        "primary_evidence_source": "html",
                        "metric_name": "outcome_accuracy",
                        "value": "0.75",
                        "item_count": "8",
                        "na_reason": "",
                    },
                    {
                        "variant_id": "flat-chunk",
                        "primary_evidence_source": "html",
                        "metric_name": "mrr",
                        "value": "0.40",
                        "item_count": "8",
                        "na_reason": "",
                    },
                ],
            )
        },
    )
    html = _render_outcome_by_stratum_html(bundle)
    assert 'id="evidence-source"' in html
    assert "Primary Evidence Source" in html
    assert "Outcome accuracy" in html
    assert "MRR" in html
    assert "0.55" in html


def test_paper_tables_html_hides_profile_and_delta() -> None:
    bundle = _bundle_with_tables([], {})
    views = build_paper_table_views(bundle)
    html = _render_tables_html(views, bundle)
    assert "By Profile" not in html
    assert "Variant Delta" not in html


def test_outcome_ordering_regression_note_when_flat_chunk_wins() -> None:
    bundle = _bundle_with_tables(
        [
            {
                "variant_id": "graph-full",
                "metric_name": "outcome_accuracy",
                "value": "0.50",
                "item_count": "5",
            },
            {
                "variant_id": "flat-chunk",
                "metric_name": "outcome_accuracy",
                "value": "0.60",
                "item_count": "5",
            },
        ],
        {
            "by_evidence_source": TableData(
                columns=[
                    "variant_id",
                    "primary_evidence_source",
                    "metric_name",
                    "value",
                    "item_count",
                    "na_reason",
                ],
                rows=[
                    {
                        "variant_id": "graph-full",
                        "primary_evidence_source": "html",
                        "metric_name": "outcome_accuracy",
                        "value": "0.40",
                        "item_count": "3",
                        "na_reason": "",
                    },
                    {
                        "variant_id": "flat-chunk",
                        "primary_evidence_source": "html",
                        "metric_name": "outcome_accuracy",
                        "value": "0.55",
                        "item_count": "3",
                        "na_reason": "",
                    },
                ],
            )
        },
    )
    notes = aggregate_investigation_notes(bundle)
    codes = [n.pattern_code for n in notes]
    assert "OUTCOME_ORDERING_REGRESSION" in codes


def test_drilldown_groups_by_item_with_variant_columns() -> None:
    from evaluation.reproduction.report_models import ItemResultRecord

    bundle = ReproOutputBundle(
        output_dir=Path("/tmp"),
        repro_run=ReproRun(
            repro_run_id="r",
            release_tag="paper-v1.0",
            manifest_hash="h",
            variant_runs=[],
        ),
        tables={},
        variant_results={
            "graph-full": [
                ItemResultRecord(
                    variant_id="graph-full",
                    item_id="item-a",
                    inspiration_profile="financebench",
                    question="What is revenue?",
                    expected_answer="100M",
                    judge_status="ok",
                    outcome_score=1.0,
                    answer_text="Revenue was 100M",
                ),
            ],
            "flat-chunk": [
                ItemResultRecord(
                    variant_id="flat-chunk",
                    item_id="item-a",
                    inspiration_profile="financebench",
                    question="What is revenue?",
                    expected_answer="100M",
                    judge_status="degraded",
                    outcome_score=0.5,
                    answer_text="About 100 million",
                ),
            ],
        },
    )
    html = _render_drilldown_html(bundle)
    assert 'id="item-item-a"' in html
    assert "Expected answer" in html
    assert "Agent answer" in html
    assert "graph-full" in html
    assert "flat-chunk" in html
    assert html.index("item-a") < html.index("variant-compare")


def test_full_report_omits_profile_and_uses_item_drilldown(tmp_path: Path) -> None:
    from evaluation.reproduction.report_loader import load_repro_report_bundle
    from fixtures.repro_report_bundle import write_minimal_repro_bundle

    root = write_minimal_repro_bundle(tmp_path / "repro")

    bundle = load_repro_report_bundle(root)
    artifact = render_html_report(bundle, tmp_path / "report.html")
    html = artifact.html_path.read_text(encoding="utf-8")
    assert "outcome-by-profile" not in html
    assert 'id="stratified"' not in html
    assert "drilldown-table" in html
    assert 'id="item-item-1"' in html
    comparison_pos = html.find('id="comparison"')
    drilldown_pos = html.find('id="drilldown"')
    assert comparison_pos != -1
    assert drilldown_pos != -1
    assert comparison_pos < drilldown_pos
