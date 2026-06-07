"""Unit tests for outcome-by-profile/stratum report sections (016)."""

from __future__ import annotations

from pathlib import Path

from evaluation.reproduction.report_models import ReproOutputBundle, TableData
from evaluation.reproduction.report_render import (
    _render_outcome_by_profile_html,
    _render_outcome_by_stratum_html,
    aggregate_investigation_notes,
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


def test_outcome_by_profile_section_renders_matrix() -> None:
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
                    {
                        "variant_id": "flat-chunk",
                        "inspiration_profile": "financebench",
                        "metric_name": "outcome_accuracy",
                        "value": "0.60",
                        "item_count": "10",
                        "na_reason": "",
                    },
                ],
            )
        },
    )
    html = _render_outcome_by_profile_html(bundle)
    assert "outcome-by-profile" in html
    assert "financebench" in html
    assert "0.8" in html


def test_outcome_by_stratum_section_renders_matrix() -> None:
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
                        "variant_id": "flat-chunk",
                        "primary_evidence_source": "html",
                        "metric_name": "outcome_accuracy",
                        "value": "0.75",
                        "item_count": "8",
                        "na_reason": "",
                    },
                ],
            )
        },
    )
    html = _render_outcome_by_stratum_html(bundle)
    assert "outcome-by-stratum" in html
    assert "html" in html


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


def test_full_report_places_outcome_sections_before_comparison(tmp_path: Path) -> None:
    from evaluation.reproduction.report_loader import load_repro_report_bundle
    from fixtures.repro_report_bundle import write_minimal_repro_bundle

    root = write_minimal_repro_bundle(tmp_path / "repro")

    bundle = load_repro_report_bundle(root)
    artifact = render_html_report(bundle, tmp_path / "report.html")
    html = artifact.html_path.read_text(encoding="utf-8")
    profile_pos = html.find("outcome-by-profile")
    comparison_pos = html.find("id=\"comparison\"")
    assert profile_pos != -1
    assert comparison_pos != -1
    assert profile_pos < comparison_pos
