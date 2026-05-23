"""Unit tests for macro pairing (008)."""

from retrieval.macro.pairing import (
    detect_quarterly_metric_cue,
    pair_qoq,
    pair_single_anchor,
    pair_yoy,
)
def test_detect_quarterly_metric_cue():
    assert detect_quarterly_metric_cue("How did revenue change?")
    assert not detect_quarterly_metric_cue("Summarize risk factors")


def test_pair_yoy_quarterly(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    refs = pair_yoy(snap, quarterly_metric=True)
    assert refs is not None
    assert len(refs) == 2
    assert refs[0].accession == "0000320193-26-000013"
    assert refs[1].accession in ("0000320193-25-000057", "0000320193-25-000073")


def test_pair_yoy_annual(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    refs = pair_yoy(snap, quarterly_metric=False)
    assert refs is not None
    assert {r.form_type for r in refs} == {"10-K"}
    assert len(refs) == 2


def test_pair_qoq(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    refs = pair_qoq(snap)
    assert refs is not None
    assert refs[0].accession == "0000320193-26-000013"
    assert refs[1].accession == "0000320193-26-000006"


def test_pair_prior_quarter(aapl_macro_snapshot):
    snap = aapl_macro_snapshot
    refs = pair_single_anchor(snap, "prior_quarter")
    assert len(refs) == 1
    assert refs[0].accession == "0000320193-26-000006"
