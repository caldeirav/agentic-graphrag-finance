#!/usr/bin/env python3
"""Build an evaluation-path demo graph and render docling-graph visualizations.

Uses docling-graph InteractiveVisualizer and ReportGenerator per:
https://github.com/docling-project/docling-graph/blob/main/docs/fundamentals/graph-management/visualization.md

The styled HTML overlay mirrors 019 investigation fields: expected vs visited section
paths, cited chunk nodes, synthesis path, and engineering failure taxonomy.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx
from docling_graph.core.utils.stats_calculator import calculate_graph_stats
from docling_graph.core.visualizers import ReportGenerator

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "assets" / "aapl-eval-graph"
EVAL_ITEMS = REPO_ROOT / "tests" / "fixtures" / "custom_judge" / "items" / "dev.jsonl"
VISUALIZATION_VERSION = "5"
AAPL_CIK = "320193"

# Stable node-type palette (legend, cytoscape base styles, and overlays share these).
NODE_TYPE_COLORS: dict[str, tuple[str, str]] = {
    "DOCUMENT": ("#bfdbfe", "#2563eb"),
    "SECTION": ("#a5f3fc", "#0891b2"),
    "CHUNK_XBRL_FACT": ("#bbf7d0", "#16a34a"),
    "CHUNK_PARAGRAPH": ("#fde68a", "#ca8a04"),
}

# Graph node ids used across scenarios (compact AAPL subgraph).
N = {
    "doc_fy2024": "doc-0000320193-24-000123",
    "doc_fy2023": "doc-0000320193-24-000076",
    "sec_item7_fy2024": "0000320193-24-000123/Item7",
    "sec_item1a": "0000320193-24-000123/Item1A",
    "sec_item7_fy2023": "0000320193-24-000076/Item7",
    "chunk_xbrl": "chunk-xbrl-net-sales-fy2024",
    "chunk_item7": "chunk-item7-p1",
    "chunk_item1a": "chunk-item1a-p1",
    "chunk_item7_old": "chunk-item7-old-p1",
}


def chunk_materialized(
    *,
    node_id: str,
    node_type: str,
    label: str,
    source_ref: str,
    properties: dict[str, str],
    bindings: dict[str, str],
) -> str:
    """Serialize full materialized chunk payload for the detail panel."""
    payload = {
        "node_id": node_id,
        "node_type": node_type,
        "label": label,
        "source_ref": source_ref,
        "properties": properties,
        "bindings": bindings,
    }
    return json.dumps(payload, indent=2)


def document_materialized(
    *,
    node_id: str,
    label: str,
    accession: str,
    form_type: str,
    period_end: str,
    cik: str,
    edgar_url: str,
) -> str:
    """Serialize document node payload for the detail panel."""
    payload = {
        "node_id": node_id,
        "node_type": "DOCUMENT",
        "label": label,
        "properties": {
            "accession": accession,
            "form_type": form_type,
            "period_end": period_end,
            "cik": cik,
        },
        "edgar_url": edgar_url,
    }
    return json.dumps(payload, indent=2)


def eval_item_fields(item: dict) -> dict[str, object]:
    """Benchmark item metadata for the investigation overlay."""
    ground_truth = item.get("ground_truth") or {}
    return {
        "question_type_tag": item.get("question_type_tag"),
        "expected_answer": ground_truth.get("answer"),
        "expected_rubric": ground_truth.get("rubric"),
        "expected_bindings": item.get("expected_bindings") or {},
        "multi_filing_required": item.get("multi_filing_required"),
        "validation_status": item.get("validation_status"),
    }


def build_edgar_url(cik: str, accession: str) -> str:
    cik_int = str(cik).lstrip("0") or "0"
    acc_nodash = accession.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{acc_nodash}/{accession}-index.htm"
    )


def build_investigation_scenarios(questions: list[dict]) -> list[dict]:
    """Demo investigation rows aligned with fixture items + a binding-miss example."""
    by_id = {row["item_id"]: row for row in questions}
    finance = by_id.get("0.0.0-financebench-001", {})
    finder = by_id.get("0.0.0-finder-001", {})
    compare = by_id.get("0.0.0-finagentbench-001", {})

    scenarios: list[dict] = [
        {
            "scenario_id": "0.0.0-financebench-001",
            **eval_item_fields(finance),
            "inspiration_profile": finance.get("inspiration_profile", "financebench"),
            "question": finance.get(
                "question",
                "What was total net sales in the most recent fiscal year?",
            ),
            "expected_section_paths": finance.get(
                "expected_section_paths",
                ["0000320193-24-000123/Item7"],
            ),
            "visited_section_paths": ["0000320193-24-000123/Item7"],
            "cited_chunk_node_ids": [N["chunk_xbrl"], N["chunk_item7"]],
            "synthesis_path": "numeric_xbrl_deterministic",
            "suggested_failure_class": None,
            "binding_miss": False,
            "highlight_nodes": [
                N["doc_fy2024"],
                N["sec_item7_fy2024"],
                N["chunk_xbrl"],
                N["chunk_item7"],
            ],
            "visited_nodes": [
                N["doc_fy2024"],
                N["sec_item7_fy2024"],
                N["chunk_xbrl"],
                N["chunk_item7"],
            ],
            "cited_nodes": [N["chunk_xbrl"], N["chunk_item7"]],
            "missing_nodes": [],
            "edgar_links": [
                {
                    "accession": "0000320193-24-000123",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                }
            ],
        },
        {
            "scenario_id": "0.0.0-finder-001",
            **eval_item_fields(finder),
            "inspiration_profile": finder.get("inspiration_profile", "finder"),
            "question": finder.get(
                "question",
                "What risk factors does the company highlight for supply chain?",
            ),
            "expected_section_paths": finder.get(
                "expected_section_paths",
                ["0000320193-24-000123/Item1A"],
            ),
            "visited_section_paths": ["0000320193-24-000123/Item1A"],
            "cited_chunk_node_ids": [N["chunk_item1a"]],
            "synthesis_path": "live_llm",
            "suggested_failure_class": None,
            "binding_miss": False,
            "highlight_nodes": [
                N["doc_fy2024"],
                N["sec_item1a"],
                N["chunk_item1a"],
            ],
            "visited_nodes": [N["doc_fy2024"], N["sec_item1a"], N["chunk_item1a"]],
            "cited_nodes": [N["chunk_item1a"]],
            "missing_nodes": [],
            "edgar_links": [
                {
                    "accession": "0000320193-24-000123",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                }
            ],
        },
        {
            "scenario_id": "0.0.0-finagentbench-001",
            **eval_item_fields(compare),
            "inspiration_profile": compare.get("inspiration_profile", "finagentbench"),
            "question": compare.get(
                "question",
                "Compare net sales discussion across the two most recent 10-K filings.",
            ),
            "expected_section_paths": compare.get(
                "expected_section_paths",
                [
                    "0000320193-24-000123/Item7",
                    "0000320193-24-000076/Item7",
                ],
            ),
            "visited_section_paths": [
                "0000320193-24-000123/Item7",
                "0000320193-24-000076/Item7",
            ],
            "cited_chunk_node_ids": [N["chunk_item7"], N["chunk_item7_old"]],
            "synthesis_path": "comparison_narrative_deterministic",
            "suggested_failure_class": None,
            "binding_miss": False,
            "highlight_nodes": [
                N["doc_fy2024"],
                N["doc_fy2023"],
                N["sec_item7_fy2024"],
                N["sec_item7_fy2023"],
                N["chunk_item7"],
                N["chunk_item7_old"],
            ],
            "visited_nodes": [
                N["doc_fy2024"],
                N["doc_fy2023"],
                N["sec_item7_fy2024"],
                N["sec_item7_fy2023"],
                N["chunk_item7"],
                N["chunk_item7_old"],
            ],
            "cited_nodes": [N["chunk_item7"], N["chunk_item7_old"]],
            "missing_nodes": [],
            "edgar_links": [
                {
                    "accession": "0000320193-24-000123",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                },
                {
                    "accession": "0000320193-24-000076",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000076"),
                },
            ],
        },
        {
            "scenario_id": "demo-binding-miss-019",
            "inspiration_profile": "investigation",
            "question_type_tag": compare.get("question_type_tag"),
            "expected_answer": (compare.get("ground_truth") or {}).get("answer"),
            "expected_rubric": (compare.get("ground_truth") or {}).get("rubric"),
            "expected_bindings": compare.get("expected_bindings") or {},
            "multi_filing_required": compare.get("multi_filing_required"),
            "validation_status": "demo",
            "question": compare.get(
                "question",
                "Compare net sales discussion across the two most recent 10-K filings.",
            ),
            "expected_section_paths": [
                "0000320193-24-000123/Item7",
                "0000320193-24-000076/Item7",
            ],
            "visited_section_paths": ["0000320193-24-000123/Item7"],
            "cited_chunk_node_ids": [N["chunk_item7"]],
            "synthesis_path": "template",
            "suggested_failure_class": "binding_error",
            "suggested_failure_detail": (
                "Macro route bound FY2024 10-K only; FY2023 Item 7 never visited"
            ),
            "binding_miss": True,
            "highlight_nodes": [
                N["doc_fy2024"],
                N["doc_fy2023"],
                N["sec_item7_fy2024"],
                N["sec_item7_fy2023"],
            ],
            "visited_nodes": [
                N["doc_fy2024"],
                N["sec_item7_fy2024"],
                N["chunk_item7"],
            ],
            "cited_nodes": [N["chunk_item7"]],
            "missing_nodes": [
                N["doc_fy2023"],
                N["sec_item7_fy2023"],
                N["chunk_item7_old"],
            ],
            "edgar_links": [
                {
                    "accession": "0000320193-24-000123",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                },
                {
                    "accession": "0000320193-24-000076",
                    "form_type": "10-K",
                    "url": build_edgar_url(AAPL_CIK, "0000320193-24-000076"),
                },
            ],
        },
    ]
    return scenarios


def build_eval_demo_graph() -> nx.DiGraph:
    """Graph aligned with custom-judge CI items (FinanceBench / FinDER / FinAgentBench style)."""
    g = nx.DiGraph()

    nodes = [
        (
            N["doc_fy2024"],
            {
                "node_type": "DOCUMENT",
                "label": "Apple 10-K FY2024",
                "display_label": "FY2024\n10-K",
                "accession": "0000320193-24-000123",
                "form_type": "10-K",
                "period_end": "2024-09-28",
                "edgar_url": build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                "eval_profiles": "financebench,finder,finagentbench",
                "materialized_json": document_materialized(
                    node_id=N["doc_fy2024"],
                    label="Apple 10-K FY2024",
                    accession="0000320193-24-000123",
                    form_type="10-K",
                    period_end="2024-09-28",
                    cik=AAPL_CIK,
                    edgar_url=build_edgar_url(AAPL_CIK, "0000320193-24-000123"),
                ),
            },
        ),
        (
            N["doc_fy2023"],
            {
                "node_type": "DOCUMENT",
                "label": "Apple 10-K FY2023",
                "display_label": "FY2023\n10-K",
                "accession": "0000320193-24-000076",
                "form_type": "10-K",
                "period_end": "2023-09-30",
                "edgar_url": build_edgar_url(AAPL_CIK, "0000320193-24-000076"),
                "eval_profiles": "finagentbench",
                "materialized_json": document_materialized(
                    node_id=N["doc_fy2023"],
                    label="Apple 10-K FY2023",
                    accession="0000320193-24-000076",
                    form_type="10-K",
                    period_end="2023-09-30",
                    cik=AAPL_CIK,
                    edgar_url=build_edgar_url(AAPL_CIK, "0000320193-24-000076"),
                ),
            },
        ),
        (
            N["sec_item7_fy2024"],
            {
                "node_type": "SECTION",
                "label": "Item 7 MD&A",
                "display_label": "Item 7\nMD&A",
                "section_path": "0000320193-24-000123/Item7",
                "eval_profiles": "financebench,finagentbench",
            },
        ),
        (
            N["sec_item1a"],
            {
                "node_type": "SECTION",
                "label": "Item 1A Risk Factors",
                "display_label": "Item 1A\nRisk Factors",
                "section_path": "0000320193-24-000123/Item1A",
                "eval_profiles": "finder",
            },
        ),
        (
            N["sec_item7_fy2023"],
            {
                "node_type": "SECTION",
                "label": "Item 7 MD&A (prior year)",
                "display_label": "Item 7\nMD&A (prior)",
                "section_path": "0000320193-24-000076/Item7",
                "eval_profiles": "finagentbench",
            },
        ),
        (
            N["chunk_xbrl"],
            {
                "node_type": "CHUNK_XBRL_FACT",
                "label": "Net sales (XBRL fact)",
                "display_label": "Net sales\n(XBRL)",
                "prop_text": "391,035 (USD millions, FY2024)",
                "prop_xbrl_concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                "prop_period": "FY2024",
                "prop_currency": "USD",
                "prop_unit": "millions",
                "prop_numeric_value": "391035",
                "eval_profiles": "financebench",
                "materialized_json": chunk_materialized(
                    node_id=N["chunk_xbrl"],
                    node_type="CHUNK_XBRL_FACT",
                    label="Net sales (XBRL fact)",
                    source_ref=(
                        "RevenueFromContractWithCustomerExcludingAssessedTax | "
                        "period=FY2024 | value=391,035 USD millions"
                    ),
                    properties={
                        "xbrl_concept": "RevenueFromContractWithCustomerExcludingAssessedTax",
                        "period": "FY2024",
                        "currency": "USD",
                        "unit": "millions",
                        "numeric_value": "391035",
                        "display_value": "391,035 (USD millions, FY2024)",
                    },
                    bindings={
                        "accession": "0000320193-24-000123",
                        "form_type": "10-K",
                        "section_path": "0000320193-24-000123/Item7",
                        "cik": AAPL_CIK,
                    },
                ),
            },
        ),
        (
            N["chunk_item7"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Net sales narrative",
                "display_label": "Net sales\nnarrative",
                "prop_text": (
                    "Net sales were $391.0 billion in fiscal 2024, an increase of 2% "
                    "compared to fiscal 2023. The increase was driven primarily by higher "
                    "net sales of iPhone and Services."
                ),
                "prop_sec_source": "XBRL",
                "eval_profiles": "financebench,finagentbench",
                "materialized_json": chunk_materialized(
                    node_id=N["chunk_item7"],
                    node_type="CHUNK_PARAGRAPH",
                    label="Net sales narrative",
                    source_ref=(
                        "Net sales were $391.0 billion in fiscal 2024, an increase of 2% "
                        "compared to fiscal 2023. The increase was driven primarily by higher "
                        "net sales of iPhone and Services."
                    ),
                    properties={
                        "sec_source": "XBRL",
                        "section_id": "Item7",
                        "paragraph_index": "1",
                    },
                    bindings={
                        "accession": "0000320193-24-000123",
                        "form_type": "10-K",
                        "section_path": "0000320193-24-000123/Item7",
                        "cik": AAPL_CIK,
                    },
                ),
            },
        ),
        (
            N["chunk_item1a"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Supply chain risks",
                "display_label": "Supply chain\nrisks",
                "prop_text": (
                    "The Company depends on single or limited sources for many components. "
                    "Supply chain disruptions, including those arising from geopolitical "
                    "events, could materially adversely affect the Company's business."
                ),
                "prop_sec_source": "HTML",
                "eval_profiles": "finder",
                "materialized_json": chunk_materialized(
                    node_id=N["chunk_item1a"],
                    node_type="CHUNK_PARAGRAPH",
                    label="Supply chain risks",
                    source_ref=(
                        "The Company depends on single or limited sources for many components. "
                        "Supply chain disruptions, including those arising from geopolitical "
                        "events, could materially adversely affect the Company's business."
                    ),
                    properties={
                        "sec_source": "HTML",
                        "section_id": "Item1A",
                        "paragraph_index": "1",
                    },
                    bindings={
                        "accession": "0000320193-24-000123",
                        "form_type": "10-K",
                        "section_path": "0000320193-24-000123/Item1A",
                        "cik": AAPL_CIK,
                    },
                ),
            },
        ),
        (
            N["chunk_item7_old"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Prior-year net sales",
                "display_label": "Prior-year\nnet sales",
                "prop_text": (
                    "Net sales were $383.3 billion in fiscal 2023, a decrease of 3% "
                    "compared to fiscal 2022, reflecting lower net sales of Products."
                ),
                "prop_sec_source": "XBRL",
                "eval_profiles": "finagentbench",
                "materialized_json": chunk_materialized(
                    node_id=N["chunk_item7_old"],
                    node_type="CHUNK_PARAGRAPH",
                    label="Prior-year net sales",
                    source_ref=(
                        "Net sales were $383.3 billion in fiscal 2023, a decrease of 3% "
                        "compared to fiscal 2022, reflecting lower net sales of Products."
                    ),
                    properties={
                        "sec_source": "XBRL",
                        "section_id": "Item7",
                        "paragraph_index": "1",
                    },
                    bindings={
                        "accession": "0000320193-24-000076",
                        "form_type": "10-K",
                        "section_path": "0000320193-24-000076/Item7",
                        "cik": AAPL_CIK,
                    },
                ),
            },
        ),
    ]
    for node_id, attrs in nodes:
        g.add_node(node_id, **attrs)

    edges = [
        (N["doc_fy2024"], N["sec_item7_fy2024"], "CONTAINS"),
        (N["doc_fy2024"], N["sec_item1a"], "CONTAINS"),
        (N["doc_fy2023"], N["sec_item7_fy2023"], "CONTAINS"),
        (N["sec_item7_fy2024"], N["chunk_xbrl"], "CONTAINS"),
        (N["sec_item7_fy2024"], N["chunk_item7"], "CONTAINS"),
        (N["sec_item1a"], N["chunk_item1a"], "CONTAINS"),
        (N["sec_item7_fy2023"], N["chunk_item7_old"], "CONTAINS"),
        (N["chunk_xbrl"], N["chunk_item7"], "NEXT"),
        (N["chunk_item7_old"], N["chunk_item7"], "REFERENCES"),
        (N["doc_fy2024"], N["doc_fy2023"], "TEMPORAL_TRANSITION"),
    ]
    for idx, (source, target, edge_type) in enumerate(edges, start=1):
        g.add_edge(
            source,
            target,
            edge_type=edge_type,
            label=edge_type,
            edge_id=f"e{idx}",
        )

    return g


def load_eval_questions() -> list[dict]:
    if not EVAL_ITEMS.is_file():
        return []
    rows: list[dict] = []
    for line in EVAL_ITEMS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_eval_context(output_dir: Path, questions: list[dict], scenarios: list[dict]) -> None:
    lines = [
        "# Evaluation paths in this graph",
        "",
        "This demo graph mirrors three accepted custom-judge items used in CI.",
        "Select a scenario in the interactive visualization to overlay **019 investigation**",
        "fields: expected vs visited section paths, cited chunk nodes, synthesis path, and",
        "engineering failure taxonomy (`binding_error`, `comparison_narrative_miss`, etc.).",
        "",
    ]
    for row in questions:
        profile = row.get("inspiration_profile", "custom")
        lines.append(f"## {profile} — `{row['item_id']}`")
        lines.append("")
        lines.append(f"**Question:** {row['question']}")
        paths = row.get("expected_section_paths") or []
        if paths:
            lines.append("")
            lines.append("**Expected section paths:**")
            for path in paths:
                lines.append(f"- `{path}`")
        scenario = next(
            (s for s in scenarios if s["scenario_id"] == row["item_id"]),
            None,
        )
        if scenario:
            lines.append("")
            lines.append(f"**Demo synthesis path:** `{scenario.get('synthesis_path')}`")
            if scenario.get("cited_chunk_node_ids"):
                lines.append("")
                lines.append("**Demo cited nodes:**")
                for node_id in scenario["cited_chunk_node_ids"]:
                    lines.append(f"- `{node_id}`")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.extend(
        [
            "## 019 binding miss demo — `demo-binding-miss-019`",
            "",
            "Illustrates `MaterializationAudit.binding_miss` when a comparison question",
            "visits FY2024 Item 7 but never opens FY2023 Item 7. Investigation pack would",
            "suggest `binding_error` and link both EDGAR filings for manual review.",
            "",
        ]
    )
    (output_dir / "eval_context.md").write_text("\n".join(lines), encoding="utf-8")


def write_investigation_overlay(output_dir: Path, scenarios: list[dict]) -> None:
    path = output_dir / "investigation_overlay.json"
    path.write_text(json.dumps(scenarios, indent=2), encoding="utf-8")


def export_graphml(graph: nx.DiGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(graph, path)


def _graph_to_cytoscape_elements(graph: nx.DiGraph) -> dict:
    nodes = []
    for node_id, attrs in graph.nodes(data=True):
        data = {"id": str(node_id), **attrs}
        data["display_label"] = data.get("display_label") or data.get("label") or str(node_id)
        nodes.append({"data": data})

    edges = []
    for idx, (source, target, attrs) in enumerate(graph.edges(data=True)):
        data = {"source": str(source), "target": str(target), **attrs}
        if "id" not in data:
            data["id"] = f"{source}-{target}-{idx}"
        edges.append({"data": data})

    return {"nodes": nodes, "edges": edges}


def _legend_type_rows() -> str:
    labels = {
        "DOCUMENT": "Document",
        "SECTION": "Section",
        "CHUNK_XBRL_FACT": "XBRL fact",
        "CHUNK_PARAGRAPH": "Paragraph chunk",
    }
    rows = []
    for node_type, (bg, border) in NODE_TYPE_COLORS.items():
        label = labels.get(node_type, node_type)
        rows.append(
            f'<div><span class="swatch" style="background:{bg};border-color:{border}"></span>'
            f"{label}</div>"
        )
    return "\n          ".join(rows)


def render_styled_visualization(
    graph: nx.DiGraph,
    output_path: Path,
    *,
    scenarios: list[dict],
) -> Path:
    """Write blog-friendly Cytoscape HTML with 019 investigation overlays."""
    elements = _graph_to_cytoscape_elements(graph)
    elements_json = json.dumps(elements, indent=2, ensure_ascii=False)
    scenarios_json = json.dumps(scenarios, indent=2, ensure_ascii=False)
    legend_types = _legend_type_rows()
    type_colors_json = json.dumps(NODE_TYPE_COLORS)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AAPL evaluation graph — agentic-graphrag-finance</title>
  <script src="https://unpkg.com/cytoscape@3.28.1/dist/cytoscape.min.js"></script>
  <script src="https://unpkg.com/dagre@0.8.5/dist/dagre.min.js"></script>
  <script src="https://unpkg.com/cytoscape-dagre@2.5.0/cytoscape-dagre.js"></script>
  <style>
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f1f5f9;
      color: #0f172a;
    }}
    #layout {{ display: flex; min-height: 100vh; }}
    #sidebar {{
      width: 280px;
      flex-shrink: 0;
      background: #fff;
      border-right: 1px solid #cbd5e1;
      padding: 0.75rem;
      overflow-y: auto;
      font-size: 0.8125rem;
    }}
    #sidebar h1 {{ margin: 0 0 0.35rem; font-size: 0.95rem; }}
    #sidebar p {{ margin: 0 0 0.75rem; color: #475569; line-height: 1.4; }}
    .scenario-btn {{
      display: block;
      width: 100%;
      text-align: left;
      margin-bottom: 0.4rem;
      padding: 0.45rem 0.55rem;
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      background: #f8fafc;
      cursor: pointer;
      font-size: 0.75rem;
    }}
    .scenario-btn.active {{ border-color: #2563eb; background: #eff6ff; }}
    #investigation-panel {{
      margin-top: 0.75rem;
      padding: 0.55rem;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      line-height: 1.45;
    }}
    #investigation-panel h2 {{ margin: 0 0 0.35rem; font-size: 0.8rem; }}
    #investigation-panel dl {{ margin: 0; }}
    #investigation-panel dt {{ font-weight: 600; margin-top: 0.35rem; }}
    #investigation-panel dd {{ margin: 0.1rem 0 0 0; color: #334155; }}
    #investigation-panel code {{ font-size: 0.68rem; word-break: break-all; }}
    #main {{ flex: 1; display: flex; flex-direction: column; min-width: 0; }}
    header {{
      padding: 0.55rem 0.75rem;
      background: #fff;
      border-bottom: 1px solid #cbd5e1;
      font-size: 0.8125rem;
    }}
    header p {{ margin: 0; color: #475569; }}
    #cy-wrap {{ position: relative; flex: 1; }}
    #cy {{ width: 100%; height: calc(100vh - 44px); background: #f8fafc; }}
    #detail-panel {{
      width: 360px;
      flex-shrink: 0;
      background: #fff;
      border-left: 1px solid #cbd5e1;
      display: none;
      flex-direction: column;
      max-height: 100vh;
    }}
    #detail-panel.open {{ display: flex; }}
    .detail-header {{
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 0.5rem;
      padding: 0.65rem 0.75rem;
      border-bottom: 1px solid #e2e8f0;
    }}
    .detail-header h2 {{ margin: 0; font-size: 0.875rem; line-height: 1.35; }}
    .detail-header p {{ margin: 0.2rem 0 0; font-size: 0.7rem; color: #64748b; }}
    #detail-close {{
      border: none;
      background: #f1f5f9;
      border-radius: 4px;
      width: 1.75rem;
      height: 1.75rem;
      cursor: pointer;
      font-size: 1rem;
      line-height: 1;
    }}
    .detail-tabs {{
      display: flex;
      border-bottom: 1px solid #e2e8f0;
      background: #f8fafc;
    }}
    .detail-tab {{
      flex: 1;
      border: none;
      background: transparent;
      padding: 0.45rem 0.5rem;
      font-size: 0.72rem;
      cursor: pointer;
      border-bottom: 2px solid transparent;
    }}
    .detail-tab.active {{
      background: #fff;
      border-bottom-color: #2563eb;
      font-weight: 600;
    }}
    .detail-body {{
      flex: 1;
      overflow: auto;
      padding: 0.65rem 0.75rem;
      font-size: 0.75rem;
      line-height: 1.45;
    }}
    .detail-body.hidden {{ display: none; }}
    .detail-body dl {{ margin: 0; }}
    .detail-body dt {{ font-weight: 600; margin-top: 0.45rem; color: #334155; }}
    .detail-body dd {{ margin: 0.1rem 0 0 0; word-break: break-word; }}
    .detail-body pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-size: 0.68rem;
      background: #f8fafc;
      border: 1px solid #e2e8f0;
      border-radius: 6px;
      padding: 0.55rem;
    }}
    .detail-excerpt {{
      background: #fffbeb;
      border: 1px solid #fde68a;
      border-radius: 6px;
      padding: 0.55rem;
      margin-top: 0.35rem;
    }}
    #legend {{
      position: absolute;
      top: 8px;
      right: 8px;
      background: rgba(255, 255, 255, 0.95);
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 0.45rem 0.55rem;
      font-size: 0.65rem;
      line-height: 1.45;
      box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }}
    #legend strong {{ display: block; margin-bottom: 0.2rem; font-size: 0.7rem; }}
    .swatch {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 2px;
      margin-right: 4px;
      vertical-align: middle;
      border: 1px solid rgba(15, 23, 42, 0.15);
    }}
    #tooltip {{
      display: none;
      position: absolute;
      max-width: 300px;
      padding: 0.5rem 0.65rem;
      background: #1e293b;
      color: #f8fafc;
      border-radius: 6px;
      font-size: 0.6875rem;
      line-height: 1.45;
      pointer-events: none;
      z-index: 10;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.25);
    }}
  </style>
</head>
<body>
  <div id="layout">
    <aside id="sidebar">
      <h1>Investigation overlay (019)</h1>
      <p>Select an evaluation item by id to highlight graph paths. Click <strong>document</strong> or <strong>chunk</strong> nodes for details in the right panel.</p>
      <div id="scenario-buttons"></div>
      <div id="investigation-panel"></div>
    </aside>
    <div id="main">
      <header>
        <p>Apple (AAPL) disclosure graph — hover for preview · click documents or chunks for the detail panel</p>
      </header>
      <div id="cy-wrap">
        <div id="legend">
          <strong>Overlay</strong>
          <div><span class="swatch" style="background:transparent;border-color:#16a34a;border-width:2px"></span>Expected ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#2563eb;border-width:2px"></span>Visited ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#ca8a04;border-width:2px"></span>Cited ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#dc2626;border-width:2px"></span>Missing ring</div>
          <strong style="margin-top:0.35rem">Node types</strong>
          {legend_types}
        </div>
        <div id="tooltip"></div>
        <div id="cy"></div>
      </div>
    </div>
    <aside id="detail-panel">
      <div class="detail-header">
        <div>
          <h2 id="detail-title">Node detail</h2>
          <p id="detail-subtitle"></p>
        </div>
        <button id="detail-close" type="button" aria-label="Close detail panel">×</button>
      </div>
      <div class="detail-tabs">
        <button type="button" class="detail-tab active" data-tab="materialized">Materialized</button>
        <button type="button" class="detail-tab" data-tab="json">JSON</button>
      </div>
      <div id="detail-materialized" class="detail-body"></div>
      <div id="detail-json" class="detail-body hidden"><pre id="detail-json-pre"></pre></div>
    </aside>
  </div>
  <script>
    const graphElements = {elements_json};
    const investigationScenarios = {scenarios_json};
    const nodeTypeColors = {type_colors_json};
    cytoscape.use(cytoscapeDagre);

    const baseNodeStyles = Object.entries(nodeTypeColors).map(([nodeType, colors]) => ({{
      selector: `node[node_type = "${{nodeType}}"]`,
      style: {{
        'background-color': colors[0],
        'border-color': colors[1],
      }},
    }}));

    const cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: [...graphElements.nodes, ...graphElements.edges],
      minZoom: 0.35,
      maxZoom: 2.5,
      wheelSensitivity: 0.2,
      style: [
        {{
          selector: 'node',
          style: {{
            'label': 'data(display_label)',
            'font-size': '9px',
            'font-family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            'color': '#0f172a',
            'text-valign': 'center',
            'text-halign': 'center',
            'text-wrap': 'wrap',
            'text-max-width': '88px',
            'width': 'label',
            'height': 'label',
            'padding': '8px',
            'shape': 'roundrectangle',
            'background-color': '#e2e8f0',
            'border-width': 1.5,
            'border-color': '#64748b',
            'opacity': 0.45,
          }},
        }},
        ...baseNodeStyles,
        {{
          selector: 'node[node_type = "DOCUMENT"]',
          style: {{ 'cursor': 'pointer' }},
        }},
        {{
          selector: 'node[node_type = "CHUNK_PARAGRAPH"], node[node_type = "CHUNK_XBRL_FACT"]',
          style: {{ 'cursor': 'pointer' }},
        }},
        {{
          selector: 'node.overlay-expected',
          style: {{ 'opacity': 1, 'border-width': 3, 'border-color': '#16a34a' }},
        }},
        {{
          selector: 'node.overlay-visited',
          style: {{ 'opacity': 1, 'border-width': 2.5, 'border-color': '#2563eb' }},
        }},
        {{
          selector: 'node.overlay-cited',
          style: {{ 'opacity': 1, 'border-width': 3.5, 'border-color': '#ca8a04' }},
        }},
        {{
          selector: 'node.overlay-missing',
          style: {{
            'opacity': 1,
            'border-width': 3,
            'border-color': '#dc2626',
            'border-style': 'dashed',
          }},
        }},
        {{
          selector: 'node.node-focused',
          style: {{ 'border-width': 4, 'border-color': '#0f172a' }},
        }},
        {{
          selector: 'edge',
          style: {{
            'width': 1.5,
            'line-color': '#94a3b8',
            'target-arrow-color': '#94a3b8',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '7px',
            'color': '#334155',
            'text-background-color': '#f8fafc',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
            'opacity': 0.35,
          }},
        }},
        {{
          selector: 'edge.overlay-active',
          style: {{ 'opacity': 1, 'line-color': '#64748b', 'target-arrow-color': '#64748b' }},
        }},
        {{
          selector: 'edge[edge_type = "TEMPORAL_TRANSITION"]',
          style: {{ 'line-color': '#dc2626', 'target-arrow-color': '#dc2626', 'line-style': 'dashed' }},
        }},
      ],
      layout: {{
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 36,
        rankSep: 52,
        edgeSep: 12,
        animate: true,
        animationDuration: 400,
      }},
    }});

    const detailPanel = document.getElementById('detail-panel');
    const detailTitle = document.getElementById('detail-title');
    const detailSubtitle = document.getElementById('detail-subtitle');
    const detailMaterialized = document.getElementById('detail-materialized');
    const detailJsonPre = document.getElementById('detail-json-pre');
    let focusedNode = null;

    function escapeHtml(value) {{
      return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
    }}

    function renderDocumentView(payload) {{
      const props = payload.properties || {{}};
      const url = payload.edgar_url || '';
      const propRows = Object.entries(props).map(
        ([key, value]) => `<dt>${{escapeHtml(key)}}</dt><dd>${{escapeHtml(value)}}</dd>`
      ).join('');
      const edgarRow = url
        ? `<dt>EDGAR filing</dt><dd><a href="${{escapeHtml(url)}}" target="_blank" rel="noopener">${{escapeHtml(url)}}</a></dd>`
        : '';
      return `
        <dl>
          <dt>node_id</dt><dd><code>${{escapeHtml(payload.node_id || '')}}</code></dd>
          <dt>node_type</dt><dd><code>${{escapeHtml(payload.node_type || '')}}</code></dd>
          <dt>label</dt><dd>${{escapeHtml(payload.label || '')}}</dd>
        </dl>
        <h3 style="font-size:0.78rem;margin:0.75rem 0 0.25rem">properties</h3>
        <dl>${{propRows || '<dd><em>none</em></dd>'}}${{edgarRow}}</dl>`;
    }}

    function renderMaterializedView(payload) {{
      const props = payload.properties || {{}};
      const bindings = payload.bindings || {{}};
      const propRows = Object.entries(props).map(
        ([key, value]) => `<dt>${{escapeHtml(key)}}</dt><dd>${{escapeHtml(value)}}</dd>`
      ).join('');
      const bindingRows = Object.entries(bindings).map(
        ([key, value]) => `<dt>${{escapeHtml(key)}}</dt><dd><code>${{escapeHtml(value)}}</code></dd>`
      ).join('');
      return `
        <dl>
          <dt>node_id</dt><dd><code>${{escapeHtml(payload.node_id || '')}}</code></dd>
          <dt>node_type</dt><dd><code>${{escapeHtml(payload.node_type || '')}}</code></dd>
          <dt>label</dt><dd>${{escapeHtml(payload.label || '')}}</dd>
          <dt>source_ref (full excerpt)</dt>
          <dd><div class="detail-excerpt">${{escapeHtml(payload.source_ref || '')}}</div></dd>
        </dl>
        <h3 style="font-size:0.78rem;margin:0.75rem 0 0.25rem">properties</h3>
        <dl>${{propRows || '<dd><em>none</em></dd>'}}</dl>
        <h3 style="font-size:0.78rem;margin:0.75rem 0 0.25rem">bindings</h3>
        <dl>${{bindingRows || '<dd><em>none</em></dd>'}}</dl>`;
    }}

    function parseNodePayload(nodeData) {{
      const raw = nodeData.materialized_json;
      if (raw) {{
        try {{
          return {{ payload: JSON.parse(raw), raw }};
        }} catch (err) {{
          return {{
            payload: {{ node_id: nodeData.id, parse_error: String(err), raw }},
            raw,
          }};
        }}
      }}
      if (nodeData.node_type === 'DOCUMENT') {{
        const payload = {{
          node_id: nodeData.id,
          node_type: 'DOCUMENT',
          label: nodeData.label,
          properties: {{
            accession: nodeData.accession,
            form_type: nodeData.form_type,
            period_end: nodeData.period_end,
          }},
          edgar_url: nodeData.edgar_url,
        }};
        return {{ payload, raw: JSON.stringify(payload, null, 2) }};
      }}
      return {{ payload: {{ node_id: nodeData.id }}, raw: '{{}}' }};
    }}

    function showDetailPanel(nodeData) {{
      const {{ payload, raw }} = parseNodePayload(nodeData);
      detailTitle.textContent = nodeData.label || nodeData.id;
      detailSubtitle.textContent = nodeData.node_type || '';
      if (payload.node_type === 'DOCUMENT') {{
        detailMaterialized.innerHTML = renderDocumentView(payload);
      }} else {{
        detailMaterialized.innerHTML = renderMaterializedView(payload);
      }}
      detailJsonPre.textContent = raw;
      detailPanel.classList.add('open');
      document.querySelectorAll('.detail-tab').forEach(tab => {{
        tab.classList.toggle('active', tab.dataset.tab === 'materialized');
      }});
      document.getElementById('detail-materialized').classList.remove('hidden');
      document.getElementById('detail-json').classList.add('hidden');
    }}

    function closeDetailPanel() {{
      detailPanel.classList.remove('open');
      if (focusedNode) {{
        focusedNode.removeClass('node-focused');
        focusedNode = null;
      }}
    }}

    document.getElementById('detail-close').onclick = closeDetailPanel;
    document.querySelectorAll('.detail-tab').forEach(tab => {{
      tab.onclick = () => {{
        document.querySelectorAll('.detail-tab').forEach(t => t.classList.remove('active'));
        tab.classList.add('active');
        const name = tab.dataset.tab;
        document.getElementById('detail-materialized').classList.toggle('hidden', name !== 'materialized');
        document.getElementById('detail-json').classList.toggle('hidden', name !== 'json');
      }};
    }});

    function renderExpectedAnswer(scenario) {{
      if (scenario.expected_answer != null && scenario.expected_answer !== '') {{
        return `<dt>Expected answer</dt><dd><code>${{escapeHtml(scenario.expected_answer)}}</code></dd>`;
      }}
      if (scenario.expected_rubric) {{
        return `<dt>Expected answer (rubric)</dt><dd>${{escapeHtml(scenario.expected_rubric)}}</dd>`;
      }}
      return `<dt>Expected answer</dt><dd><em>not specified</em></dd>`;
    }}

    function renderBindings(bindings) {{
      if (!bindings || !Object.keys(bindings).length) {{
        return '<dd><em>none</em></dd>';
      }}
      return Object.entries(bindings).map(
        ([key, value]) => `<dt>${{escapeHtml(key)}}</dt><dd><code>${{escapeHtml(
          Array.isArray(value) ? value.join(', ') : value
        )}}</code></dd>`
      ).join('');
    }}

    function renderPanel(scenario) {{
      const panel = document.getElementById('investigation-panel');
      const failure = scenario.suggested_failure_class
        ? `<dt>Failure class</dt><dd><code>${{scenario.suggested_failure_class}}</code></dd>`
        : '';
      const detail = scenario.suggested_failure_detail
        ? `<dt>Detail</dt><dd>${{scenario.suggested_failure_detail}}</dd>` : '';
      panel.innerHTML = `
        <h2><code>${{escapeHtml(scenario.scenario_id)}}</code></h2>
        <dl>
          <dt>Profile</dt><dd>${{escapeHtml(scenario.inspiration_profile || '')}}</dd>
          <dt>Question type</dt><dd><code>${{escapeHtml(scenario.question_type_tag || '')}}</code></dd>
          <dt>Question</dt><dd>${{escapeHtml(scenario.question || '')}}</dd>
          ${{renderExpectedAnswer(scenario)}}
          <dt>Expected sections</dt><dd>${{(scenario.expected_section_paths || []).map(p => `<code>${{escapeHtml(p)}}</code>`).join('<br>') || '<em>none</em>'}}</dd>
          <dt>Expected bindings</dt>
          ${{renderBindings(scenario.expected_bindings)}}
        </dl>
        <h3 style="font-size:0.78rem;margin:0.85rem 0 0.35rem">Demo trace</h3>
        <dl>
          <dt>Synthesis path</dt><dd><code>${{escapeHtml(scenario.synthesis_path || 'unknown')}}</code></dd>
          <dt>Binding miss</dt><dd>${{scenario.binding_miss ? 'yes' : 'no'}}</dd>
          ${{failure}}${{detail}}
          <dt>Visited sections</dt><dd>${{(scenario.visited_section_paths || []).map(p => `<code>${{escapeHtml(p)}}</code>`).join('<br>') || '<em>none</em>'}}</dd>
        </dl>`;
    }}

    function applyScenario(scenario) {{
      cy.nodes().removeClass('overlay-expected overlay-visited overlay-cited overlay-missing');
      cy.edges().removeClass('overlay-active');
      (scenario.highlight_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-expected'));
      (scenario.visited_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-visited'));
      (scenario.cited_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-cited'));
      (scenario.missing_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-missing'));
      cy.edges().forEach(edge => {{
        const src = edge.source().id();
        const tgt = edge.target().id();
        const active = (scenario.visited_nodes || []).includes(src) && (scenario.visited_nodes || []).includes(tgt);
        if (active) edge.addClass('overlay-active');
      }});
      renderPanel(scenario);
    }}

    const btnWrap = document.getElementById('scenario-buttons');
    investigationScenarios.forEach((scenario, idx) => {{
      const btn = document.createElement('button');
      btn.className = 'scenario-btn' + (idx === 0 ? ' active' : '');
      btn.textContent = scenario.scenario_id;
      btn.onclick = () => {{
        document.querySelectorAll('.scenario-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        applyScenario(scenario);
      }};
      btnWrap.appendChild(btn);
    }});
    applyScenario(investigationScenarios[0]);

    const tooltip = document.getElementById('tooltip');
    cy.on('mouseover', 'node', (evt) => {{
      const d = evt.target.data();
      const clickHint = (d.node_type === 'DOCUMENT' || d.node_type === 'CHUNK_PARAGRAPH' || d.node_type === 'CHUNK_XBRL_FACT')
        ? 'Click for node detail'
        : null;
      const lines = [
        `<strong>${{d.label || d.id}}</strong>`,
        d.node_type ? `Type: ${{d.node_type}}` : null,
        d.section_path ? `Path: ${{d.section_path}}` : null,
        d.prop_text ? (d.prop_text.length > 120 ? d.prop_text.slice(0, 120) + '…' : d.prop_text) : null,
        d.prop_xbrl_concept ? `Concept: ${{d.prop_xbrl_concept}}` : null,
        clickHint,
      ].filter(Boolean);
      tooltip.innerHTML = lines.join('<br>');
      tooltip.style.display = 'block';
    }});
    cy.on('mouseout', 'node', () => {{ tooltip.style.display = 'none'; }});
    cy.on('mousemove', (evt) => {{
      tooltip.style.left = (evt.originalEvent.pageX + 12) + 'px';
      tooltip.style.top = (evt.originalEvent.pageY + 12) + 'px';
    }});

    cy.on('tap', 'node', (evt) => {{
      const node = evt.target;
      const d = node.data();
      if (focusedNode) focusedNode.removeClass('node-focused');
      if (
        d.node_type === 'DOCUMENT'
        || d.node_type === 'CHUNK_PARAGRAPH'
        || d.node_type === 'CHUNK_XBRL_FACT'
      ) {{
        focusedNode = node;
        node.addClass('node-focused');
        showDetailPanel(d);
        return;
      }}
      closeDetailPanel();
    }});

    cy.on('tap', (evt) => {{
      if (evt.target === cy) closeDetailPanel();
    }});
  </script>
</body>
</html>
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Directory for visualization.html, report.md, graph_stats.json",
    )
    args = parser.parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    questions = load_eval_questions()
    scenarios = build_investigation_scenarios(questions)
    graph = build_eval_demo_graph()
    export_graphml(graph, output_dir / "eval_demo.graphml")

    html_path = render_styled_visualization(
        graph,
        output_dir / "visualization.html",
        scenarios=scenarios,
    )

    report_path = output_dir / "report.md"
    ReportGenerator().visualize(graph, report_path, source_model_count=2, include_samples=True)

    metadata = calculate_graph_stats(graph, source_model_count=2)
    stats_path = output_dir / "graph_stats.json"
    stats_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    write_eval_context(output_dir, questions, scenarios)
    write_investigation_overlay(output_dir, scenarios)

    index_html = output_dir / "index.html"
    index_html.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=visualization.html?v={VISUALIZATION_VERSION}">
  <title>AAPL evaluation graph</title>
</head>
<body>
  <p><a href="visualization.html?v={VISUALIZATION_VERSION}">Open the interactive graph</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )

    print(f"Wrote {html_path}")
    print(f"Wrote {report_path}")
    print(f"Wrote {stats_path}")
    print(f"Wrote {output_dir / 'investigation_overlay.json'}")
    print(f"Nodes: {metadata.node_count}, edges: {metadata.edge_count}")


if __name__ == "__main__":
    main()
