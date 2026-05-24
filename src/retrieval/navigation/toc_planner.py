"""Filing TOC planner for LLM-driven meso section discovery (009 A/C)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from graph.accession import document_root_id
from models.enums import GraphEdgeType, GraphNodeType, NarrativeSectionKind
from models.filing import FilingRef
from models.graph import GraphNode, GraphSnapshot
from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.orchestration.llm import create_chat_llm
from retrieval.orchestration.meso_scoring import is_mda_query, is_risk_only_query
from tracing.console_trace.llm import traced_llm_invoke


class TocEntry(BaseModel):
    section_node_id: str
    section_id: str
    label: str
    narrative_kind: str
    item_number: str = ""
    child_chunk_count: int = 0


class TocPlanResult(BaseModel):
    accession: str
    ranked_section_node_ids: list[str] = Field(default_factory=list)
    primary_narrative_kind: str = ""
    exclude_kinds: list[str] = Field(default_factory=list)
    excluded_section_node_ids: list[str] = Field(default_factory=list)
    rationale: str = ""
    proposal_source: str = "llm"


def _child_chunk_count(snapshot: GraphSnapshot, section_node_id: str) -> int:
    count = 0
    for edge in snapshot.edges:
        if edge.source_id != section_node_id or edge.edge_type != GraphEdgeType.CONTAINS:
            continue
        for node in snapshot.nodes:
            if node.node_id == edge.target_id and node.node_type in (
                GraphNodeType.CHUNK_TABLE,
                GraphNodeType.CHUNK_ROW,
                GraphNodeType.CHUNK_PARAGRAPH,
                GraphNodeType.CHUNK_XBRL_FACT,
            ):
                count += 1
    return count


def build_filing_toc(snapshot: GraphSnapshot, filing: FilingRef) -> list[TocEntry]:
    doc_id = document_root_id(filing.accession)
    entries: list[TocEntry] = []
    for node in snapshot.nodes:
        if node.node_type != GraphNodeType.SECTION:
            continue
        if not node.node_id.startswith(doc_id):
            continue
        props = node.properties or {}
        entries.append(
            TocEntry(
                section_node_id=node.node_id,
                section_id=str(props.get("section_id", "")),
                label=(node.label or "")[:200],
                narrative_kind=str(props.get("narrative_kind", "other")),
                item_number=str(props.get("item_number", "")),
                child_chunk_count=_child_chunk_count(snapshot, node.node_id),
            )
        )
    entries.sort(key=lambda e: (e.item_number or "Z", e.section_id))
    return entries[:40]


def _mock_plan(query: str, toc: list[TocEntry], filing: FilingRef) -> TocPlanResult:
    q = query.lower()
    by_kind: dict[str, list[TocEntry]] = {}
    for entry in toc:
        by_kind.setdefault(entry.narrative_kind, []).append(entry)

    exclude_kinds: list[str] = []
    ranked: list[str] = []

    if is_mda_query(q):
        primary = NarrativeSectionKind.MD_AND_A.value
        exclude_kinds = [NarrativeSectionKind.RISK_FACTORS.value, "xbrl_bucket"]
        ranked = [e.section_node_id for e in by_kind.get(primary, [])]
        if not ranked:
            ranked = [
                e.section_node_id
                for e in toc
                if "md_and_a" in e.section_id or "mda" in e.section_id
            ]
    elif is_risk_only_query(q):
        primary = NarrativeSectionKind.RISK_FACTORS.value
        exclude_kinds = [NarrativeSectionKind.MD_AND_A.value, "xbrl_bucket"]
        ranked = [e.section_node_id for e in by_kind.get(primary, [])]
    elif is_financial_numeric_query(q):
        primary = "xbrl_bucket"
        exclude_kinds = []
        ranked = [e.section_node_id for e in by_kind.get("xbrl_bucket", [])]
        ranked += [
            e.section_node_id
            for e in toc
            if e.narrative_kind not in ("xbrl_bucket",)
            and any(k in e.label.lower() for k in ("financial", "income", "balance"))
        ][:2]
    else:
        primary = "other"
        ranked = [e.section_node_id for e in toc if e.narrative_kind not in ("xbrl_bucket",)]

    if not ranked:
        ranked = [e.section_node_id for e in toc if e.narrative_kind != "xbrl_bucket"][:3]

    excluded_ids = [
        e.section_node_id
        for e in toc
        if e.narrative_kind in exclude_kinds
    ]
    return TocPlanResult(
        accession=filing.accession,
        ranked_section_node_ids=ranked[:3],
        primary_narrative_kind=primary,
        exclude_kinds=exclude_kinds,
        excluded_section_node_ids=excluded_ids,
        rationale=f"mock toc: primary={primary}",
        proposal_source="mock",
    )


def is_financial_numeric_query(query: str) -> bool:
    q = query.lower()
    if is_mda_query(q):
        return False
    return any(
        k in q
        for k in (
            "revenue",
            "sales",
            "net sales",
            "income",
            "earnings",
            "assets",
            "eps",
            "year over year",
            "year-over-year",
            "yoy",
            "quarter over quarter",
            "qoq",
        )
    )


def apply_toc_heuristics(
    query: str, plan: TocPlanResult, toc: list[TocEntry]
) -> TocPlanResult:
    """Deterministic overrides when the TOC LLM picks the wrong Item for common intents."""
    q = query.lower()
    by_kind: dict[str, list[TocEntry]] = {}
    for entry in toc:
        by_kind.setdefault(entry.narrative_kind, []).append(entry)

    if is_mda_query(q):
        mda = by_kind.get(NarrativeSectionKind.MD_AND_A.value, [])
        if not mda:
            mda = [e for e in toc if "md_and_a" in e.section_id or "mda" in e.section_id]
        if mda:
            return plan.model_copy(
                update={
                    "ranked_section_node_ids": [e.section_node_id for e in mda][:3],
                    "primary_narrative_kind": NarrativeSectionKind.MD_AND_A.value,
                    "exclude_kinds": [
                        NarrativeSectionKind.RISK_FACTORS.value,
                        "xbrl_bucket",
                    ],
                    "rationale": (plan.rationale or "") + " [heuristic: MD&A query]",
                }
            )

    if is_financial_numeric_query(q):
        xbrl = by_kind.get("xbrl_bucket", [])
        if xbrl:
            return plan.model_copy(
                update={
                    "ranked_section_node_ids": [e.section_node_id for e in xbrl][:3],
                    "primary_narrative_kind": "xbrl_bucket",
                    "exclude_kinds": [
                        NarrativeSectionKind.BUSINESS_DESCRIPTION.value,
                        NarrativeSectionKind.MD_AND_A.value,
                        NarrativeSectionKind.RISK_FACTORS.value,
                    ],
                    "rationale": (plan.rationale or "") + " [heuristic: numeric/yoy -> XBRL]",
                }
            )

    return plan


def _validate_plan(plan: TocPlanResult, toc: list[TocEntry], *, query: str = "") -> TocPlanResult:
    plan = apply_toc_heuristics(query, plan, toc)
    allowed = {e.section_node_id for e in toc}
    ranked = [sid for sid in plan.ranked_section_node_ids if sid in allowed]
    excluded = [sid for sid in plan.excluded_section_node_ids if sid in allowed]
    exclude_kinds = list(plan.exclude_kinds)
    if not ranked and toc:
        if is_financial_numeric_query(query):
            ranked = [e.section_node_id for e in toc if e.narrative_kind == "xbrl_bucket"]
        elif is_mda_query(query):
            ranked = [
                e.section_node_id
                for e in toc
                if e.narrative_kind == NarrativeSectionKind.MD_AND_A.value
            ]
        if not ranked:
            ranked = [toc[0].section_node_id]
    return plan.model_copy(
        update={
            "ranked_section_node_ids": ranked[:3],
            "excluded_section_node_ids": excluded,
            "exclude_kinds": exclude_kinds,
            "primary_narrative_kind": plan.primary_narrative_kind,
        }
    )


def plan_meso_sections_toc(
    *,
    query: str,
    filing: FilingRef,
    toc: list[TocEntry],
    form_type: str = "10-K",
) -> TocPlanResult:
    if not toc:
        return TocPlanResult(
            accession=filing.accession,
            rationale="empty toc",
            proposal_source="mock",
        )

    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        return _validate_plan(_mock_plan(query, toc, filing), toc, query=query)

    toc_json = [e.model_dump() for e in toc]
    system = (
        "You route SEC filing questions to the correct Item/section using the filing table of contents. "
        "10-K structure: Item 1 Business; Item 1A Risk Factors (standalone statutory risks); "
        "Item 7 MD&A (management discussion including operational risks and outlook); "
        "financial statements/notes; xbrl_bucket = tagged numeric facts only. "
        "When the question asks about risks IN MD&A, choose md_and_a sections and EXCLUDE risk_factors (Item 1A). "
        "For revenue, net sales, earnings, assets, or year-over-year change questions, choose xbrl_bucket first "
        "(tagged XBRL facts), NOT Item 1 business description. "
        "Return JSON only: "
        '{"ranked_section_node_ids":["..."],"primary_narrative_kind":"md_and_a|risk_factors|...","'
        '"exclude_kinds":["risk_factors"],"excluded_section_node_ids":[],"rationale":"..."}'
    )
    human = json.dumps(
        {
            "question": query,
            "form_type": form_type,
            "accession": filing.accession,
            "sections": toc_json,
        },
        indent=0,
    )[:12000]
    llm = create_chat_llm(temperature=0)
    resp, _ = traced_llm_invoke("meso_toc_planner", llm, [SystemMessage(content=system), HumanMessage(content=human)])
    data = extract_json_from_llm(resp.content or "")
    ranked = [str(x) for x in (data.get("ranked_section_node_ids") or []) if x]
    plan = TocPlanResult(
        accession=filing.accession,
        ranked_section_node_ids=ranked,
        primary_narrative_kind=str(data.get("primary_narrative_kind", "")),
        exclude_kinds=[str(k) for k in (data.get("exclude_kinds") or [])],
        excluded_section_node_ids=[str(x) for x in (data.get("excluded_section_node_ids") or [])],
        rationale=str(data.get("rationale", ""))[:500],
        proposal_source="llm",
    )
    return _validate_plan(plan, toc, query=query)


def load_toc_mock_override(query: str, source_node_id: str) -> TocPlanResult | None:
    """Optional fixture override (tests)."""
    q = query.lower()
    name = None
    if is_mda_query(q):
        name = "mda_risk"
    elif "revenue" in q:
        name = "revenue_xbrl"
    if not name:
        return None
    path = Path("tests/fixtures/navigation_planner/toc") / f"{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get("accession"):
        return TocPlanResult.model_validate(data)
    return None
