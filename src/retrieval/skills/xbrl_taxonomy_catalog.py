"""Taxonomy-aware XBRL fact catalog skill for agent resolution (023 v2)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent
from retrieval.skills.xbrl_concept_guards import query_concept_family
from retrieval.skills.xbrl_concept_roles import infer_concept_taxonomy
from retrieval.skills.xbrl_fact_catalog import (
    XbrlFactCatalogEntry,
    build_xbrl_fact_catalog,
    is_xbrl_evidence_chunk,
)
from retrieval.skills.xbrl_graph_chunks import collect_filing_xbrl_chunks, merge_xbrl_evidence

CATALOG_SCHEMA_VERSION = "2.0.0"

RESOLUTION_AGENT_FIELDS = (
    "chunk_id",
    "concept",
    "standard_label",
    "metric_roles",
    "statement_role",
    "value_display",
    "period_start",
    "period_end",
    "is_annual",
    "segment_hint",
)


class XbrlFactCatalogEntryV2(XbrlFactCatalogEntry):
    """V1 catalog row plus taxonomy metadata for LLM role mapping."""

    model_config = ConfigDict(extra="allow")

    standard_label: str = ""
    metric_roles: list[str] = Field(default_factory=list)
    statement_role: str = "other"
    period_type: str = "unknown"
    accession: str = ""
    schema_version: str = CATALOG_SCHEMA_VERSION

    def for_agent_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chunk_id": self.chunk_id,
            "concept": self.concept,
            "standard_label": self.standard_label,
            "metric_roles": self.metric_roles,
            "statement_role": self.statement_role,
            "value_display": self.value_display,
            "period_end": self.period_end,
            "is_annual": self.is_annual,
        }
        if self.period_start:
            payload["period_start"] = self.period_start
        if self.segment_hint:
            payload["segment_hint"] = self.segment_hint
        if self.matches_query:
            payload["matches_query"] = True
        return payload


class XbrlTaxonomyCatalog(BaseModel):
    """Agent-facing catalog bundle with schema version and filing context."""

    model_config = ConfigDict(extra="allow")

    schema_version: str = CATALOG_SCHEMA_VERSION
    temporal_anchor: str = ""
    filing_accessions: list[str] = Field(default_factory=list)
    entries: list[XbrlFactCatalogEntryV2] = Field(default_factory=list)

    def for_agent(self, limit: int = 40) -> list[dict[str, Any]]:
        return [entry.for_agent_dict() for entry in self.entries[:limit]]

    def entries_with_role(self, role: str) -> list[XbrlFactCatalogEntryV2]:
        return [entry for entry in self.entries if role in entry.metric_roles]


def infer_period_type(*, is_annual: bool, period_start: str, period_end: str) -> str:
    if is_annual:
        return "annual"
    if period_start and period_end and period_start != period_end:
        return "interim"
    if period_end and not period_start:
        return "instant"
    return "unknown"


def enrich_catalog_entry(
    entry: XbrlFactCatalogEntry,
    *,
    accession: str = "",
) -> XbrlFactCatalogEntryV2:
    roles, statement_role, standard_label = infer_concept_taxonomy(entry.concept)
    return XbrlFactCatalogEntryV2(
        **entry.model_dump(),
        standard_label=standard_label,
        metric_roles=roles,
        statement_role=statement_role,
        period_type=infer_period_type(
            is_annual=entry.is_annual,
            period_start=entry.period_start,
            period_end=entry.period_end,
        ),
        accession=accession,
    )


def trim_catalog_for_resolution(
    entries: list[XbrlFactCatalogEntryV2],
    query: str,
    metric_intent: MetricIntent | None,
    *,
    micro_chunk_ids: set[str] | None = None,
    limit: int = 50,
) -> list[XbrlFactCatalogEntryV2]:
    """Keep micro evidence + role-relevant rows when the filing index is large."""
    if len(entries) <= limit:
        return entries
    micro_chunk_ids = micro_chunk_ids or set()
    pinned = [e for e in entries if e.chunk_id in micro_chunk_ids]
    pool = [e for e in entries if e.chunk_id not in micro_chunk_ids]

    roles: list[str] = []
    family = query_concept_family(query, metric_intent)
    if metric_intent and metric_intent.metric_type == "ratio":
        if family == "margin":
            roles = ["net_income", "total_revenue", "revenue", "margin_denominator", "margin_numerator"]
        elif family == "tax_rate":
            roles = ["pretax_income", "net_income"]
        elif family == "dividend_payout":
            roles = ["net_income", "total_revenue"]
        else:
            roles = ["net_income", "total_revenue", "revenue"]
    elif metric_intent and metric_intent.metric_type == "point":
        roles = ["total_equity", "net_income", "total_revenue", "total_assets", "operating_cash_flow"]

    selected: list[XbrlFactCatalogEntryV2] = list(pinned)
    seen = {e.chunk_id for e in selected}
    if roles:
        for role in roles:
            for entry in rank_entries_by_metric_role(pool, role):
                if entry.chunk_id in seen:
                    continue
                selected.append(entry)
                seen.add(entry.chunk_id)
                if len(selected) >= limit:
                    return selected[:limit]
    annual = sorted(
        [e for e in pool if e.chunk_id not in seen],
        key=lambda e: (int(e.is_annual), e.period_end),
        reverse=True,
    )
    for entry in annual:
        if entry.chunk_id in seen:
            continue
        selected.append(entry)
        seen.add(entry.chunk_id)
        if len(selected) >= limit:
            break
    return selected[:limit]


def build_taxonomy_catalog(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    state: dict | None = None,
    temporal_intent: TemporalScopeIntent | None = None,
    metric_intent: MetricIntent | None = None,
    temporal_anchor: str = "",
    graph_api=None,
    snapshot_id: str = "",
) -> XbrlTaxonomyCatalog:
    """Build period-filtered catalog from micro evidence plus filing-level XBRL index."""
    filing_chunks = collect_filing_xbrl_chunks(graph_api, snapshot_id, filing_set)
    merged_evidence = merge_xbrl_evidence(evidence, filing_chunks)
    micro_ids = {c.chunk_node_id for c in evidence if is_xbrl_evidence_chunk(c)}

    accession_by_chunk: dict[str, str] = {}
    for filing in filing_set:
        acc = filing.accession or ""
        if not acc:
            continue
        for chunk in merged_evidence:
            if acc in (chunk.accession or "") or acc in (chunk.section_id or "") or acc in chunk.excerpt[:120]:
                accession_by_chunk[chunk.chunk_node_id] = acc
    for chunk in filing_chunks:
        if chunk.accession:
            accession_by_chunk[chunk.chunk_node_id] = chunk.accession

    base_entries = build_xbrl_fact_catalog(
        merged_evidence,
        query,
        filing_set,
        state=state,
        temporal_intent=temporal_intent,
        metric_intent=metric_intent,
    )
    default_accession = filing_set[0].accession if filing_set else ""
    enriched = [
        enrich_catalog_entry(
            entry,
            accession=accession_by_chunk.get(entry.chunk_id, default_accession),
        )
        for entry in base_entries
    ]
    trimmed = trim_catalog_for_resolution(
        enriched,
        query,
        metric_intent,
        micro_chunk_ids=micro_ids,
    )
    return XbrlTaxonomyCatalog(
        temporal_anchor=temporal_anchor,
        filing_accessions=[f.accession for f in filing_set if f.accession],
        entries=trimmed,
    )


def catalog_entries_for_resolution(
    entries: list[XbrlFactCatalogEntry | XbrlFactCatalogEntryV2],
    *,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Compact JSON rows for XBRL resolution prompts."""
    out: list[dict[str, Any]] = []
    for entry in entries[:limit]:
        if isinstance(entry, XbrlFactCatalogEntryV2):
            out.append(entry.for_agent_dict())
        else:
            out.append(enrich_catalog_entry(entry).for_agent_dict())
    return out


def rank_entries_by_metric_role(
    entries: list[XbrlFactCatalogEntryV2],
    role: str,
    *,
    prefer_annual: bool = True,
) -> list[XbrlFactCatalogEntryV2]:
    """Rank catalog rows for a target metric role (deterministic tie-breaks)."""

    def score(entry: XbrlFactCatalogEntryV2) -> tuple[int, int, int]:
        role_hit = 10 if role in entry.metric_roles else 0
        if role == "net_income" and "pretax_income" in entry.metric_roles:
            role_hit -= 6
        if role in ("margin_denominator", "total_revenue", "revenue") and "total_revenue" in entry.metric_roles:
            role_hit += 2
        annual_boost = 3 if prefer_annual and entry.is_annual else 0
        query_boost = 2 if entry.matches_query else 0
        return role_hit + annual_boost + query_boost, int(entry.is_annual), len(entry.period_end)

    return sorted(entries, key=score, reverse=True)


def persist_taxonomy_catalog_on_state(state: dict | None, catalog: XbrlTaxonomyCatalog) -> None:
    if state is None or not isinstance(state, dict):
        return
    state["xbrl_taxonomy_catalog_json"] = catalog.model_dump_json()
