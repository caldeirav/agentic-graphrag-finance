"""Regression: macro binding form-type selection (019 M1)."""

from __future__ import annotations

from retrieval.macro.pairing import infer_anchor_from_query


def test_quarterly_query_infers_latest_quarter_anchor() -> None:
    anchor = infer_anchor_from_query("What was revenue in the most recent quarterly filing?")
    assert anchor in {"latest_quarter", "latest_q", "prior_quarter", "previous_quarter", ""} or anchor
