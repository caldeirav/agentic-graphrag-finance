"""Unit tests for repro slice expansion (022-C)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from evaluation.reproduction.slice_expansion import expand_slice_accessions
from models.filing import FilingRef
from models.graph import GraphManifest, GraphSnapshot
from retrieval.skills.metric_intent import heuristic_metric_intent
from retrieval.skills.temporal_scope import infer_temporal_scope_intent


def test_yoy_expands_prior_year_10k(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    acc_2025 = "0000034088-26-000045"
    acc_2024 = "0000034088-25-000010"
    ref = MagicMock()
    ref.ticker = "XOM"
    ref.snapshot_id = "snap-xom"

    manifest = GraphManifest(
        created_at=date(2026, 1, 1),
        filing_refs=[
            FilingRef(
                cik="34088",
                accession=acc_2025,
                form_type="10-K",
                filed_at=date(2026, 2, 1),
                period_end=date(2025, 12, 31),
                source_uri="",
            ),
            FilingRef(
                cik="34088",
                accession=acc_2024,
                form_type="10-K",
                filed_at=date(2025, 2, 1),
                period_end=date(2024, 12, 31),
                source_uri="",
            ),
        ],
        parser_version="1",
        graph_builder_version="1",
        storage_path="x",
        node_count=1,
        edge_count=0,
    )
    snapshot = GraphSnapshot(
        snapshot_id="snap-xom",
        issuer_id="XOM",
        nodes=[],
        edges=[],
        manifest=manifest,
    )

    index = MagicMock()
    index.resolve_accessions.return_value = [ref]
    index.graphs_dir = tmp_path

    monkeypatch.setattr(
        "evaluation.reproduction.slice_expansion.load_snapshot",
        lambda ticker, sid, base: snapshot,
    )

    query = "What was the year-over-year change in net income for fiscal year 2025?"
    temporal = infer_temporal_scope_intent(query, fiscal_period_labels=["FY2025"])
    metric = heuristic_metric_intent(query)
    expanded = expand_slice_accessions(
        [acc_2025],
        index,
        query=query,
        temporal_intent=temporal,
        metric_intent=metric,
    )
    assert acc_2025 in expanded
    assert acc_2024 in expanded


def test_point_query_does_not_expand() -> None:
    index = MagicMock()
    index.resolve_accessions.side_effect = AssertionError("should not resolve")
    query = "What was total shareholder equity for fiscal year 2025?"
    expanded = expand_slice_accessions(
        ["0000034088-26-000045"],
        index,
        query=query,
        temporal_intent=infer_temporal_scope_intent(query, fiscal_period_labels=["FY2025"]),
        metric_intent=heuristic_metric_intent(query),
    )
    assert expanded == ["0000034088-26-000045"]
