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
VISUALIZATION_VERSION = "3"
AAPL_CIK = "320193"

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
            "label": "FinanceBench — numeric lookup",
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
            "label": "FinDER — risk narrative",
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
            "label": "FinAgentBench — comparison (success)",
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
            "label": "019 — binding miss (comparison)",
            "inspiration_profile": "investigation",
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
                "eval_profiles": "financebench",
            },
        ),
        (
            N["chunk_item7"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Net sales narrative",
                "display_label": "Net sales\nnarrative",
                "prop_text": "Net sales were $391.0 billion in fiscal 2024.",
                "prop_sec_source": "XBRL",
                "eval_profiles": "financebench,finagentbench",
            },
        ),
        (
            N["chunk_item1a"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Supply chain risks",
                "display_label": "Supply chain\nrisks",
                "prop_text": "The Company depends on single or limited sources for many components.",
                "prop_sec_source": "HTML",
                "eval_profiles": "finder",
            },
        ),
        (
            N["chunk_item7_old"],
            {
                "node_type": "CHUNK_PARAGRAPH",
                "label": "Prior-year net sales",
                "display_label": "Prior-year\nnet sales",
                "prop_text": "Net sales were $383.3 billion in fiscal 2023.",
                "prop_sec_source": "XBRL",
                "eval_profiles": "finagentbench",
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
      width: 300px;
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
      <p>Select a scenario to highlight expected paths, agent visits, citations, and failure taxonomy signals on the graph.</p>
      <div id="scenario-buttons"></div>
      <div id="investigation-panel"></div>
    </aside>
    <div id="main">
      <header>
        <p>Apple (AAPL) disclosure graph — hover nodes · drag to pan · scroll to zoom</p>
      </header>
      <div id="cy-wrap">
        <div id="legend">
          <strong>Overlay</strong>
          <div><span class="swatch" style="background:#dcfce7;border-color:#16a34a"></span>Expected path</div>
          <div><span class="swatch" style="background:#dbeafe;border-color:#2563eb"></span>Visited</div>
          <div><span class="swatch" style="background:#fef3c7;border-color:#ca8a04"></span>Cited</div>
          <div><span class="swatch" style="background:#fee2e2;border-color:#dc2626"></span>Expected but missing</div>
          <strong style="margin-top:0.35rem">Node types</strong>
          <div><span class="swatch" style="background:#bfdbfe;border-color:#2563eb"></span>Document</div>
          <div><span class="swatch" style="background:#a5f3fc;border-color:#0891b2"></span>Section</div>
          <div><span class="swatch" style="background:#bbf7d0;border-color:#16a34a"></span>XBRL fact</div>
        </div>
        <div id="tooltip"></div>
        <div id="cy"></div>
      </div>
    </div>
  </div>
  <script>
    const graphElements = {elements_json};
    const investigationScenarios = {scenarios_json};
    cytoscape.use(cytoscapeDagre);

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
        {{
          selector: 'node[node_type = "DOCUMENT"]',
          style: {{ 'background-color': '#bfdbfe', 'border-color': '#2563eb' }},
        }},
        {{
          selector: 'node[node_type = "SECTION"]',
          style: {{ 'background-color': '#a5f3fc', 'border-color': '#0891b2' }},
        }},
        {{
          selector: 'node[node_type = "CHUNK_XBRL_FACT"]',
          style: {{ 'background-color': '#bbf7d0', 'border-color': '#16a34a' }},
        }},
        {{
          selector: 'node[node_type = "CHUNK_PARAGRAPH"][prop_sec_source = "HTML"]',
          style: {{ 'background-color': '#e9d5ff', 'border-color': '#9333ea' }},
        }},
        {{
          selector: 'node[node_type = "CHUNK_PARAGRAPH"][prop_sec_source = "XBRL"]',
          style: {{ 'background-color': '#fde68a', 'border-color': '#ca8a04' }},
        }},
        {{
          selector: 'node.overlay-expected',
          style: {{ 'opacity': 1, 'border-width': 2.5, 'border-color': '#16a34a', 'background-color': '#dcfce7' }},
        }},
        {{
          selector: 'node.overlay-visited',
          style: {{ 'opacity': 1, 'border-color': '#2563eb' }},
        }},
        {{
          selector: 'node.overlay-cited',
          style: {{ 'border-width': 3, 'border-color': '#ca8a04', 'background-color': '#fef3c7' }},
        }},
        {{
          selector: 'node.overlay-missing',
          style: {{ 'opacity': 1, 'border-width': 2.5, 'border-color': '#dc2626', 'background-color': '#fee2e2', 'line-style': 'dashed' }},
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

    function renderPanel(scenario) {{
      const panel = document.getElementById('investigation-panel');
      const failure = scenario.suggested_failure_class
        ? `<dt>Failure class</dt><dd><code>${{scenario.suggested_failure_class}}</code></dd>`
        : `<dt>Failure class</dt><dd><em>none (happy path)</em></dd>`;
      const detail = scenario.suggested_failure_detail
        ? `<dt>Detail</dt><dd>${{scenario.suggested_failure_detail}}</dd>` : '';
      const edgar = (scenario.edgar_links || []).map(l =>
        `<li><a href="${{l.url}}" target="_blank" rel="noopener">${{l.form_type}} ${{l.accession}}</a></li>`
      ).join('');
      panel.innerHTML = `
        <h2>${{scenario.label}}</h2>
        <dl>
          <dt>Question</dt><dd>${{scenario.question}}</dd>
          <dt>Synthesis path</dt><dd><code>${{scenario.synthesis_path || 'unknown'}}</code></dd>
          <dt>Binding miss</dt><dd>${{scenario.binding_miss ? 'yes' : 'no'}}</dd>
          ${{failure}}${{detail}}
          <dt>Expected sections</dt><dd>${{(scenario.expected_section_paths || []).map(p => `<code>${{p}}</code>`).join('<br>')}}</dd>
          <dt>Visited sections</dt><dd>${{(scenario.visited_section_paths || []).map(p => `<code>${{p}}</code>`).join('<br>')}}</dd>
          <dt>EDGAR</dt><dd><ul style="margin:0;padding-left:1rem">${{edgar}}</ul></dd>
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
      btn.textContent = scenario.label;
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
      const lines = [
        `<strong>${{d.label || d.id}}</strong>`,
        d.node_type ? `Type: ${{d.node_type}}` : null,
        d.section_path ? `Path: ${{d.section_path}}` : null,
        d.prop_text ? d.prop_text : null,
        d.prop_xbrl_concept ? `Concept: ${{d.prop_xbrl_concept}}` : null,
        d.edgar_url ? `<a href="${{d.edgar_url}}" style="color:#93c5fd">EDGAR filing</a>` : null,
        d.eval_profiles ? `Eval: ${{d.eval_profiles}}` : null,
      ].filter(Boolean);
      tooltip.innerHTML = lines.join('<br>');
      tooltip.style.display = 'block';
    }});
    cy.on('mouseout', 'node', () => {{ tooltip.style.display = 'none'; }});
    cy.on('mousemove', (evt) => {{
      tooltip.style.left = (evt.originalEvent.pageX + 12) + 'px';
      tooltip.style.top = (evt.originalEvent.pageY + 12) + 'px';
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
