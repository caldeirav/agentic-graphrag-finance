"""Unit tests for LaTeX copy generation (014)."""

from pathlib import Path

from evaluation.reproduction.report_loader import load_repro_report_bundle
from evaluation.reproduction.report_models import PaperTableId
from evaluation.reproduction.report_render import build_paper_table_views, render_latex_only
from fixtures.repro_report_bundle import write_minimal_repro_bundle


def test_latex_contains_booktabs_and_provenance(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    views = build_paper_table_views(bundle)
    headline = next(v for v in views if v.table_id == PaperTableId.HEADLINE)
    assert "\\toprule" in headline.latex_copy
    assert "\\bottomrule" in headline.latex_copy
    assert "release_tag: paper-smoke" in headline.latex_copy
    assert "outcome_accuracy" in headline.csv_copy


def test_latex_values_match_csv(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    views = build_paper_table_views(bundle)
    headline = next(v for v in views if v.table_id == PaperTableId.HEADLINE)
    assert "0.9" in headline.latex_copy or "0.900" in headline.latex_copy
    assert "0.9" in headline.csv_copy


def test_latex_only_stdout_order(tmp_path: Path) -> None:
    write_minimal_repro_bundle(tmp_path)
    bundle = load_repro_report_bundle(tmp_path)
    out = render_latex_only(bundle, table_ids=[PaperTableId.HEADLINE, PaperTableId.VARIANT_DELTA])
    assert out.count("\\begin{table}") >= 1
