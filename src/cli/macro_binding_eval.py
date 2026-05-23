"""Macro binding benchmark eval (008) — filing-set match only."""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import MagicMock

from evaluation.datasets.finagentbench import FinAgentBenchDataset
from evaluation.metrics.macro_binding import macro_binding_accuracy, multi_filing_rate
from graph.legacy_builder import build_snapshot
from models.filing import FilingRef
from models.parsing import ParsedDocument
from retrieval.orchestration.nodes.macro_router import macro_router


def build_aapl_macro_eval_snapshot():
    """Same filing set as tests/conftest aapl_macro_snapshot."""
    refs = [
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000013",
            form_type="10-Q",
            filed_at=date(2026, 5, 1),
            period_end=date(2026, 3, 28),
            source_uri="u1",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000006",
            form_type="10-Q",
            filed_at=date(2026, 1, 30),
            period_end=date(2025, 12, 27),
            source_uri="u2",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000057",
            form_type="10-Q",
            filed_at=date(2025, 5, 2),
            period_end=date(2025, 6, 28),
            source_uri="u3",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000073",
            form_type="10-Q",
            filed_at=date(2025, 2, 1),
            period_end=date(2025, 3, 29),
            source_uri="u3b",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000079",
            form_type="10-K",
            filed_at=date(2025, 10, 31),
            period_end=date(2025, 9, 27),
            source_uri="u4",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-24-000123",
            form_type="10-K",
            filed_at=date(2024, 11, 1),
            period_end=date(2024, 9, 28),
            source_uri="u5",
        ),
    ]
    docs = [
        ParsedDocument(
            filing=r,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="test",
            content_hash=r.accession,
        )
        for r in refs
    ]
    return build_snapshot("AAPL", docs, snapshot_id="macro-bench")


def run_macro_binding_eval(
    *,
    ticker: str = "AAPL",
    min_accuracy: float = 0.70,
    min_multi_rate: float = 0.80,
) -> dict:
    os.environ["USE_MOCK_LLM"] = "1"
    items = FinAgentBenchDataset().load_macro_binding_slice()
    if not items:
        return {"passed": False, "total": 0, "hits": 0, "error": "macro_binding.jsonl missing"}

    snap = build_aapl_macro_eval_snapshot()
    api = MagicMock()
    api.get_snapshot.return_value = snap

    predicted: dict[str, list[str]] = {}
    for item in items:
        if item.expect_binding_failure:
            predicted[item.item_id] = []
            continue
        out = macro_router(
            {
                "query": item.question,
                "snapshot_id": snap.snapshot_id,
                "filing_set": [],
                "cli_prebound": False,
            },
            graph_api=api,
        )
        if out.get("macro_binding_failed"):
            predicted[item.item_id] = []
        else:
            predicted[item.item_id] = [f.accession for f in out.get("filing_set") or []]

    accuracy = macro_binding_accuracy(predicted, items)
    mfr = multi_filing_rate(items)
    hits = sum(
        1
        for item in items
        if set(predicted.get(item.item_id, []))
        == set((item.expected_bindings.accessions if item.expected_bindings else []) or [])
    )
    passed = (
        accuracy >= min_accuracy
        and mfr >= min_multi_rate
        and len(items) >= 50
    )
    return {
        "passed": passed,
        "total": len(items),
        "hits": hits,
        "macro_binding_accuracy": accuracy,
        "multi_filing_rate": mfr,
        "ticker": ticker,
    }
