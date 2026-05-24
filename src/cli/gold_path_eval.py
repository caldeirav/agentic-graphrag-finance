"""Gold-path navigation benchmark runner (009)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from evaluation.datasets.finagentbench import FinAgentBenchDataset
from evaluation.fixtures.navigation_eval_snapshot import build_navigation_eval_snapshot
from evaluation.metrics.gold_path import (
    chunk_reach_rate,
    is_full_graph_scan,
    path_match_rate,
    sequence_matches_pattern,
)
from graph.query_api import LocalGraphQueryAPI
from graph.store import save_snapshot
from retrieval.navigation.models import NavigationTraceRecord
from retrieval.navigation.walker import run_meso_navigation, run_micro_navigation


def _evaluate_item(item: dict, snapshot, graph_api) -> dict:
    accessions = set(item.get("expected_accessions") or [])
    filings = [f for f in snapshot.manifest.filing_refs if f.accession in accessions]
    if not filings:
        filings = list(snapshot.manifest.filing_refs[:1])

    state = {
        "query": item["query"],
        "snapshot_id": snapshot.snapshot_id,
        "filing_set": filings,
    }
    meso_out = run_meso_navigation(state, graph_api=graph_api)
    state.update(meso_out)
    micro_out = run_micro_navigation(state, graph_api=graph_api)

    required = set(item.get("required_chunk_node_ids") or [])
    chunk_ids = {c.chunk_node_id for c in micro_out.get("evidence_chunks") or []}
    if required:
        reached = required.issubset(chunk_ids)
    else:
        reached = len(chunk_ids) > 0

    trace = micro_out.get("navigation_trace")
    if isinstance(trace, dict):
        trace = NavigationTraceRecord.model_validate(trace)
    scan_ratio = float(trace.scan_ratio) if trace else 0.0
    full_scan = is_full_graph_scan(scan_ratio)
    if full_scan and required:
        reached = False

    path_matched = False
    patterns = item.get("acceptable_edge_sequences") or []
    if trace and patterns:
        for path in trace.micro_paths + trace.meso_paths:
            if sequence_matches_pattern(path.edge_type_sequence, patterns):
                path_matched = True
                break
    else:
        path_matched = reached

    return {
        "item_id": item.get("id", ""),
        "reached": reached,
        "path_matched": path_matched,
        "scan_ratio": scan_ratio,
        "full_scan": full_scan,
    }


def run_gold_path_eval(
    *,
    fixtures_dir: Path | None = None,
    min_reach: float = 0.75,
    min_path: float = 0.90,
) -> dict:
    os.environ["USE_MOCK_LLM"] = "1"
    items = FinAgentBenchDataset().load_gold_path_slice(fixtures_dir)
    if not items:
        return {"passed": False, "total": 0, "hits": 0, "error": "gold_path.jsonl missing"}

    snap = build_navigation_eval_snapshot()
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        save_snapshot(snap, base)
        api = LocalGraphQueryAPI(base, snap.issuer_id)
        results = [_evaluate_item(row, snap, api) for row in items]

    reach = chunk_reach_rate(results)
    path = path_match_rate(results)
    hits = sum(1 for r in results if r.get("reached"))
    passed = len(items) >= 40 and reach >= min_reach and path >= min_path
    return {
        "chunk_reach_rate": reach,
        "path_match_rate": path,
        "total": len(items),
        "hits": hits,
        "passed": passed,
        "min_items": 40,
    }
