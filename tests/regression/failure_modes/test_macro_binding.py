"""Regression: macro binding form-type selection (019 M1)."""

from __future__ import annotations

from retrieval.macro.models import MacroBindingProposal
from retrieval.macro.pairing import infer_anchor_from_query, materialize_proposal_filings


def test_quarterly_query_infers_latest_quarter_anchor() -> None:
    anchor = infer_anchor_from_query("What was revenue in the most recent quarterly filing?")
    assert anchor == "latest_quarter"


def test_annual_query_infers_latest_annual_anchor() -> None:
    anchor = infer_anchor_from_query("Summarize risk factors in the latest 10-K annual report.")
    assert anchor == "latest_annual"


def test_materialize_prefers_10q_for_quarterly_revenue_question(aapl_macro_snapshot) -> None:
    proposal = MacroBindingProposal(
        intent_summary="Quarterly revenue",
        anchor="latest_quarter",
        quarterly_metric_cue=True,
    )
    refs = materialize_proposal_filings(
        proposal,
        aapl_macro_snapshot,
        query="What was revenue in the most recent quarterly 10-Q filing?",
    )
    assert refs is not None
    assert len(refs) == 1
    assert refs[0].form_type == "10-Q"
