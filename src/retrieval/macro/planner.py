"""LLM macro binding planner (008)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from models.enums import ComparisonMode
from models.graph import GraphSnapshot
from retrieval.macro.llm_json import extract_json_from_llm, parse_comparison_mode
from retrieval.macro.models import MacroBindingProposal, ProposalSource
from retrieval.macro.pairing import detect_quarterly_metric_cue, infer_anchor_from_query
from retrieval.orchestration.llm import create_chat_llm
from tracing.console_trace.llm import traced_llm_invoke


def _fixture_dir() -> Path:
    return Path("tests/fixtures/macro_planner")


def _load_mock_proposal(query: str) -> MacroBindingProposal | None:
    q = query.lower()
    fixtures = {
        "prior_quarter": ("prior quarter", "previous quarter"),
        "latest_quarter": ("latest quarter", "this quarter"),
        "latest_annual": ("annual report", "latest 10-k", "risk factor"),
        "yoy_revenue": ("year over year", "yoy"),
        "qoq_compare": ("quarter over quarter", "qoq", "previous quarter compared"),
    }
    for name, cues in fixtures.items():
        if any(c in q for c in cues):
            path = _fixture_dir() / f"{name}.json"
            if path.exists():
                data = json.loads(path.read_text())
                mode_raw = data.get("comparison_mode")
                if mode_raw:
                    data["comparison_mode"] = parse_comparison_mode(mode_raw).value
                return MacroBindingProposal.model_validate(data)
    return None


def _manifest_summary(snapshot: GraphSnapshot, limit: int = 20) -> str:
    refs = list(snapshot.manifest.filing_refs)[:limit]
    rows = [
        {
            "accession": r.accession,
            "form_type": r.form_type,
            "period_end": str(r.period_end),
        }
        for r in refs
    ]
    return json.dumps(rows, default=str)


def _apply_metric_cue(proposal: MacroBindingProposal, query: str) -> MacroBindingProposal:
    cue = detect_quarterly_metric_cue(query)
    if proposal.quarterly_metric_cue == cue:
        return proposal
    return proposal.model_copy(update={"quarterly_metric_cue": cue})


def plan_macro_binding(
    query: str,
    snapshot: GraphSnapshot,
) -> tuple[MacroBindingProposal, dict]:
    """Return proposal and optional trace patch from LLM invoke."""
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        mock = _load_mock_proposal(query)
        if mock is not None:
            return _apply_metric_cue(mock, query), {}
        refs = list(snapshot.manifest.filing_refs or [])
        forms = {r.form_type.upper() for r in refs}
        inferred = infer_anchor_from_query(query)
        if inferred:
            anchor = inferred
        elif forms == {"10-K"} or (forms and "10-Q" not in forms):
            anchor = "latest_annual"
        elif detect_quarterly_metric_cue(query) and "10-Q" in forms:
            anchor = "latest_quarter"
        elif len(refs) == 1:
            anchor = None
        else:
            anchor = "latest_quarter"
        mock = MacroBindingProposal(
            intent_summary=query[:200],
            anchor=anchor,
            proposed_accessions=[refs[0].accession] if len(refs) == 1 else [],
            comparison_mode=ComparisonMode.YOY if detect_quarterly_metric_cue(query) else None,
            is_comparison=False,
            quarterly_metric_cue=detect_quarterly_metric_cue(query),
            proposal_source=ProposalSource.DETERMINISTIC,
        )
        return _apply_metric_cue(mock, query), {}

    llm = create_chat_llm()
    manifest_json = _manifest_summary(snapshot)
    prompt = (
        f"Question: {query}\n"
        f"Available filings: {manifest_json}\n"
        "Return JSON with intent_summary, comparison_mode (none|yoy|qoq|sequential), "
        "anchor (latest_quarter|prior_quarter|latest_annual|null), period_labels, "
        "proposed_accessions, is_comparison, quarterly_metric_cue."
    )
    messages = [
        SystemMessage(content="You are a financial disclosure macro routing agent."),
        HumanMessage(content=prompt),
    ]
    resp, trace_patch = traced_llm_invoke("macro_router", llm, messages)
    text = resp.content if isinstance(resp.content, str) else str(resp.content)
    data = extract_json_from_llm(text)
    if not data:
        return MacroBindingProposal(
            intent_summary=query[:200],
            proposal_source=ProposalSource.LLM,
            raw_llm_text=text[:500],
        ), trace_patch

    mode_raw = data.get("comparison_mode")
    mode = None
    if mode_raw and str(mode_raw).lower() not in ("none", "null", ""):
        mode = parse_comparison_mode(mode_raw)

    proposal = MacroBindingProposal(
        intent_summary=str(data.get("intent_summary") or query),
        comparison_mode=mode,
        anchor=data.get("anchor") if data.get("anchor") not in (None, "null") else None,
        period_labels=list(data.get("period_labels") or []),
        proposed_accessions=list(data.get("proposed_accessions") or []),
        is_comparison=bool(data.get("is_comparison")),
        quarterly_metric_cue=bool(data.get("quarterly_metric_cue")),
        proposal_source=ProposalSource.LLM,
        raw_llm_text=text[:500],
    )
    return _apply_metric_cue(proposal, query), trace_patch
