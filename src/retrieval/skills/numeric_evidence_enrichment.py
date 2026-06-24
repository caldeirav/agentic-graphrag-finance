"""Retrieval enrichment for multi-fact numeric metrics (023 M2/M3)."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field

from graph.accession import accession_from_node_id
from models.enums import EvidenceSourceType, GraphNodeType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.metric_intent import MetricIntent, heuristic_metric_intent
from retrieval.skills.xbrl_concept_guards import query_concept_family
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry, build_xbrl_fact_catalog, parse_xbrl_excerpt
from retrieval.skills.xbrl_taxonomy_catalog import enrich_catalog_entry, rank_entries_by_metric_role

_FAMILY_PATTERNS: dict[str, list[tuple[str, re.Pattern[str]]]] = {
    "margin": [
        (
            "income",
            re.compile(
                r"NetIncome(?:Loss)?|ProfitLoss|OperatingIncomeLoss|IncomeLossFromContinuingOperations",
                re.I,
            ),
        ),
        (
            "revenue",
            re.compile(
                r"RevenueFromContractWithCustomer|Revenues?|SalesRevenueNet|TotalRevenues?",
                re.I,
            ),
        ),
    ],
    "tax_rate": [
        ("tax", re.compile(r"IncomeTaxExpense|ProvisionForIncomeTax|EffectiveIncomeTax", re.I)),
        (
            "pretax",
            re.compile(
                r"EarningsBeforeIncomeTax|IncomeBeforeIncomeTax|PretaxIncome|ProfitBeforeTax",
                re.I,
            ),
        ),
    ],
    "dividend_payout": [
        ("dividends", re.compile(r"Dividends(?:Paid)?|DistributionsTo(?:Shareholders|Stockholders)", re.I)),
        ("income", re.compile(r"NetIncome(?:Loss)?|ProfitLoss", re.I)),
    ],
}

_FAMILY_RANK_ROLE: dict[str, str | None] = {
    "income": "net_income",
    "revenue": "total_revenue",
    "pretax": "pretax_income",
    "tax": None,
    "dividends": None,
}


@dataclass
class NumericEvidenceEnrichmentResult:
    evidence: list[EvidenceChunk]
    added_chunk_ids: list[str] = field(default_factory=list)
    missing_families: list[str] = field(default_factory=list)
    trace: dict = field(default_factory=dict)


def _ratio_family_key(query: str, metric_intent: MetricIntent) -> str:
    return query_concept_family(query, metric_intent) or "margin"


def _required_families(metric_intent: MetricIntent, query: str) -> list[str]:
    if metric_intent.metric_type != "ratio":
        return []
    patterns = _FAMILY_PATTERNS.get(_ratio_family_key(query, metric_intent), _FAMILY_PATTERNS["margin"])
    return [name for name, _ in patterns]


def _families_present(
    evidence: list[EvidenceChunk],
    query: str,
    metric_intent: MetricIntent,
) -> set[str]:
    xbrl = [c for c in evidence if "XBRL" in (getattr(c.source_type, "value", str(c.source_type)) or "")]
    if not xbrl:
        return set()
    catalog = build_xbrl_fact_catalog(xbrl, query, [], metric_intent=metric_intent)
    patterns = _FAMILY_PATTERNS.get(_ratio_family_key(query, metric_intent), _FAMILY_PATTERNS["margin"])
    present: set[str] = set()
    for name, pattern in patterns:
        if any(pattern.search(entry.concept) for entry in catalog):
            present.add(name)
    return present


def _node_to_chunk(node, accession: str) -> EvidenceChunk:
    excerpt = (node.source_ref or node.label or "").strip()
    return EvidenceChunk(
        chunk_node_id=node.node_id,
        excerpt=excerpt[:2000],
        content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
        citation_label=(node.label or "XBRL")[:80],
        source_type=EvidenceSourceType.XBRL,
        accession=accession,
        section_id=str((node.properties or {}).get("section_id", "XBRL")),
    )


def _catalog_entry_from_node(node, accession: str) -> XbrlFactCatalogEntry | None:
    excerpt = (node.source_ref or node.label or "").strip()
    concept = str((node.properties or {}).get("xbrl_concept") or node.label or "")
    parsed = parse_xbrl_excerpt(excerpt)
    if not parsed and not concept:
        return None
    if not parsed:
        parsed = {"concept": concept, "value_display": "", "value_raw": "", "period_start": "", "period_end": ""}
    return XbrlFactCatalogEntry(
        chunk_id=node.node_id,
        concept=parsed.get("concept") or concept,
        value_raw=parsed.get("value_raw", ""),
        value_display=parsed.get("value_display", ""),
        period_start=parsed.get("period_start", ""),
        period_end=parsed.get("period_end", ""),
        is_annual=parsed.get("is_annual") == "True",
    )


def _pick_best_node_for_family(
    candidates: list[tuple],
    family_name: str,
) -> tuple | None:
    if not candidates:
        return None
    role = _FAMILY_RANK_ROLE.get(family_name)
    if not role:
        return candidates[0]
    ranked_entries: list[tuple[XbrlFactCatalogEntry, tuple]] = []
    for item in candidates:
        node, accession, concept = item
        base = _catalog_entry_from_node(node, accession)
        if base is None:
            continue
        ranked_entries.append((enrich_catalog_entry(base, accession=accession), item))
    if not ranked_entries:
        return candidates[0]
    best = rank_entries_by_metric_role([entry for entry, _ in ranked_entries], role)[0]
    for entry, item in ranked_entries:
        if entry.chunk_id == best.chunk_id:
            return item
    return candidates[0]


def enrich_numeric_evidence(
    evidence: list[EvidenceChunk],
    query: str,
    filing_set: list[FilingRef],
    *,
    snapshot_id: str,
    graph_api,
    metric_intent: MetricIntent | None = None,
) -> NumericEvidenceEnrichmentResult:
    """Add missing XBRL fact families from bound filings before numeric synthesis."""
    intent = metric_intent or heuristic_metric_intent(query)
    required = _required_families(intent, query)
    if not required or not filing_set or not snapshot_id:
        return NumericEvidenceEnrichmentResult(evidence=list(evidence))

    present = _families_present(evidence, query, intent)
    missing = [name for name in required if name not in present]
    if not missing:
        return NumericEvidenceEnrichmentResult(evidence=list(evidence))

    family_key = _ratio_family_key(query, intent)
    patterns = _FAMILY_PATTERNS.get(family_key, _FAMILY_PATTERNS["margin"])
    pattern_by_name = {name: pat for name, pat in patterns}

    snap = graph_api.get_snapshot(snapshot_id)
    filing_accessions = {f.accession for f in filing_set}
    existing_ids = {c.chunk_node_id for c in evidence}
    added_chunks: list[EvidenceChunk] = []
    added_ids: list[str] = []
    still_missing = list(missing)
    candidates_by_family: dict[str, list[tuple]] = {name: [] for name in still_missing}

    for node in snap.nodes:
        if node.node_type != GraphNodeType.CHUNK_XBRL_FACT:
            continue
        accession = accession_from_node_id(node.node_id)
        if accession not in filing_accessions:
            continue
        if node.node_id in existing_ids:
            continue
        concept = str((node.properties or {}).get("xbrl_concept") or node.label or "")
        for family_name in still_missing:
            pattern = pattern_by_name.get(family_name)
            if pattern is None or not pattern.search(concept):
                continue
            candidates_by_family[family_name].append((node, accession, concept))

    for family_name in list(still_missing):
        picked = _pick_best_node_for_family(candidates_by_family.get(family_name, []), family_name)
        if picked is None:
            continue
        node, accession, _concept = picked
        added_chunks.append(_node_to_chunk(node, accession))
        added_ids.append(node.node_id)
        existing_ids.add(node.node_id)
        still_missing.remove(family_name)

    trace = {
        "missing_families_before": missing,
        "added_chunk_ids": added_ids,
        "metric_type": intent.metric_type,
        "ratio_family": family_key,
        "ranked_selection": True,
    }
    return NumericEvidenceEnrichmentResult(
        evidence=list(evidence) + added_chunks,
        added_chunk_ids=added_ids,
        missing_families=still_missing,
        trace=trace,
    )


def enrichment_trace_json(result: NumericEvidenceEnrichmentResult) -> str:
    return json.dumps(result.trace)
