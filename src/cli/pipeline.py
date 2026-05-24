"""End-to-end pipeline: fetch → parse → graph → query."""

from __future__ import annotations

import json
from pathlib import Path

from cli.corpus_pipeline import run_ask_pipeline as _run_ask_corpus
from graph.builder import build_snapshot
from ingestion import fetch_filing
from models.ingestion import CLIAskRequest, CLIAskResult
from parsing.sec_download_adapter import parse_from_cache


def run_ask_pipeline(request: CLIAskRequest) -> CLIAskResult:
    return _run_ask_corpus(request)


def run_test_pipeline(
    *,
    ticker: str | None = None,
    cik: str | None = None,
    accession: str | None = None,
    form_type: str = "10-K",
    force_refresh: bool = False,
    min_sections: int = 1,
    min_chunk_tables: int = 0,
    check_registry: bool = False,
) -> dict:
    from models.ingestion import CLITestResult

    entry = fetch_filing(
        ticker=ticker,
        cik=cik,
        accession=accession,
        form_type=form_type,
        force_refresh=force_refresh,
    )
    doc = parse_from_cache(entry)
    issuer = ticker.upper() if ticker else doc.filing.cik
    snapshot = build_snapshot(issuer, [doc])
    messages: list[str] = []
    node_counts = {
        "sections": len(doc.sections),
        "tables": len(doc.tables),
        "graph_nodes": len(snapshot.nodes),
    }
    passed = node_counts["sections"] >= min_sections and node_counts["tables"] >= min_chunk_tables
    if not passed:
        messages.append(
            f"Thresholds not met: sections>={min_sections}, tables>={min_chunk_tables}"
        )

    if check_registry:
        reg_path = Path("specs/002-live-disclosure-cli/contracts/cli-test-registry.json")
        if reg_path.exists():
            reg = json.loads(reg_path.read_text())
            min_sections = max(min_sections, int(reg.get("min_sections", 1)))
            min_chunk_tables = max(min_chunk_tables, int(reg.get("min_chunk_tables", 0)))
            passed = (
                node_counts["sections"] >= min_sections
                and node_counts["tables"] >= min_chunk_tables
            )

    result = CLITestResult(
        passed=passed,
        node_counts=node_counts,
        cache_entry_path=str(entry.local_path),
        messages=messages,
    )
    return result.model_dump()
