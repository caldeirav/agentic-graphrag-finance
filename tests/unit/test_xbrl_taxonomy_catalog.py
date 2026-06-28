"""Unit tests for taxonomy-aware XBRL catalog skill (023 v2)."""

from __future__ import annotations

import json
import re
from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.skills.xbrl_concept_roles import ConceptRoleRule, register_concept_role_rules
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry, build_xbrl_fact_catalog
from retrieval.skills.xbrl_taxonomy_catalog import (
    CATALOG_SCHEMA_VERSION,
    build_taxonomy_catalog,
    catalog_entries_for_resolution,
    enrich_catalog_entry,
    rank_entries_by_metric_role,
)


def _chunk(chunk_id: str, excerpt: str) -> EvidenceChunk:
    return EvidenceChunk(
        chunk_node_id=chunk_id,
        excerpt=excerpt,
        content_hash="h",
        citation_label="XBRL",
        source_type=EvidenceSourceType.XBRL,
        section_id="XBRL",
    )


def _filing() -> FilingRef:
    return FilingRef(
        cik="34088",
        accession="0000034088-26-000045",
        form_type="10-K",
        filed_at=date(2026, 2, 1),
        period_end=date(2025, 12, 31),
        source_uri="",
    )


def test_enrich_catalog_entry_assigns_metric_roles() -> None:
    entry = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="ni",
            concept="ProfitLoss",
            value_display="$29.76 billion USD",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    assert "net_income" in entry.metric_roles
    assert entry.statement_role == "income_statement"
    assert entry.standard_label == "Net income (loss)"
    assert entry.schema_version == CATALOG_SCHEMA_VERSION


def test_rank_net_income_prefers_profit_loss_over_pretax() -> None:
    pretax = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="pretax",
            concept="IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
            value_display="$36.55 billion USD",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    net = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="ni",
            concept="ProfitLoss",
            value_display="$29.76 billion USD",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    ranked = rank_entries_by_metric_role([pretax, net], "net_income")
    assert ranked[0].concept == "ProfitLoss"
    assert "pretax_income" in ranked[1].metric_roles


def test_build_taxonomy_catalog_enriches_period_filtered_rows() -> None:
    evidence = [
        _chunk(
            "rev",
            "XBRL TotalRevenuesAndOtherIncome: $326.00 billion USD "
            "for period 2025-01-01 - 2025-12-31",
        ),
        _chunk(
            "ni",
            "XBRL ProfitLoss: $29.76 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    query = "What was net income ProfitLoss for fiscal year 2025?"
    filing = _filing()
    base = build_xbrl_fact_catalog(evidence, query, [filing])
    catalog = build_taxonomy_catalog(evidence, query, [filing])
    assert catalog.schema_version == CATALOG_SCHEMA_VERSION
    assert catalog.filing_accessions == ["0000034088-26-000045"]
    assert len(catalog.entries) == len(base)
    assert catalog.entries
    by_concept = {entry.concept: entry for entry in catalog.entries}
    if "ProfitLoss" in by_concept:
        assert "net_income" in by_concept["ProfitLoss"].metric_roles
    if "TotalRevenuesAndOtherIncome" in by_concept:
        assert "margin_denominator" in by_concept["TotalRevenuesAndOtherIncome"].metric_roles


def test_catalog_entries_for_resolution_uses_agent_projection() -> None:
    entry = enrich_catalog_entry(
        XbrlFactCatalogEntry(
            chunk_id="ni",
            concept="ProfitLoss",
            value_display="$29.76 billion USD",
            period_end="2025-12-31",
            is_annual=True,
        )
    )
    rows = catalog_entries_for_resolution([entry])
    assert rows[0]["standard_label"] == "Net income (loss)"
    assert rows[0]["metric_roles"] == ["net_income", "margin_numerator"]
    assert "value_raw" not in rows[0]


def test_register_concept_role_rules_extends_inference() -> None:
    register_concept_role_rules(
        [
            ConceptRoleRule(
                re.compile(r"^CustomMetric$"),
                ("custom_role",),
                "other",
                "Custom metric label",
            )
        ]
    )
    enriched = enrich_catalog_entry(
        XbrlFactCatalogEntry(chunk_id="c", concept="CustomMetric", value_display="$1.00")
    )
    assert enriched.metric_roles == ["custom_role"]
    assert enriched.standard_label == "Custom metric label"


def test_taxonomy_catalog_json_matches_contract_shape() -> None:
    evidence = [
        _chunk(
            "fy",
            "XBRL StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest: "
            "$216.10 billion USD for period 2025-01-01 - 2025-12-31",
        ),
    ]
    base = build_xbrl_fact_catalog(
        evidence,
        "What was total shareholder equity for fiscal year 2025?",
        [_filing()],
    )
    catalog = build_taxonomy_catalog(
        evidence,
        "What was total shareholder equity for fiscal year 2025?",
        [_filing()],
    )
    payload = json.loads(catalog.model_dump_json())
    assert payload["schema_version"] == "3.0.0"
    assert payload["entries"]
    assert payload["entries"][0]["metric_roles"]
    assert len(catalog.entries) == len(base)
