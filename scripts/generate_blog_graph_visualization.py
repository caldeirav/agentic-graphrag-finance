#!/usr/bin/env python3
"""Build an evaluation-path demo graph and render docling-graph visualizations.

Uses docling-graph InteractiveVisualizer and ReportGenerator per:
https://github.com/docling-project/docling-graph/blob/main/docs/fundamentals/graph-management/visualization.md
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


def build_eval_demo_graph() -> nx.DiGraph:
    """Graph aligned with custom-judge CI items (FinanceBench / FinDER / FinAgentBench style)."""
    g = nx.DiGraph()

    nodes = [
        (
            "doc-0000320193-24-000123",
            {
                "node_type": "DOCUMENT",
                "label": "Apple 10-K FY2024",
                "display_label": "FY2024\n10-K",
                "accession": "0000320193-24-000123",
                "form_type": "10-K",
                "period_end": "2024-09-28",
            },
        ),
        (
            "doc-0000320193-24-000076",
            {
                "node_type": "DOCUMENT",
                "label": "Apple 10-K FY2023",
                "display_label": "FY2023\n10-K",
                "accession": "0000320193-24-000076",
                "form_type": "10-K",
                "period_end": "2023-09-30",
            },
        ),
        (
            "0000320193-24-000123/Item7",
            {
                "node_type": "SECTION",
                "label": "Item 7 MD&A",
                "display_label": "Item 7\nMD&A",
                "section_path": "0000320193-24-000123/Item7",
            },
        ),
        (
            "0000320193-24-000123/Item1A",
            {
                "node_type": "SECTION",
                "label": "Item 1A Risk Factors",
                "display_label": "Item 1A\nRisk Factors",
                "section_path": "0000320193-24-000123/Item1A",
            },
        ),
        (
            "0000320193-24-000076/Item7",
            {
                "node_type": "SECTION",
                "label": "Item 7 MD&A (prior year)",
                "display_label": "Item 7\nMD&A (prior)",
                "section_path": "0000320193-24-000076/Item7",
            },
        ),
        (
            "chunk-xbrl-net-sales-fy2024",
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
            "chunk-item7-p1",
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
            "chunk-item1a-p1",
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
            "chunk-item7-old-p1",
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
        ("doc-0000320193-24-000123", "0000320193-24-000123/Item7", "CONTAINS"),
        ("doc-0000320193-24-000123", "0000320193-24-000123/Item1A", "CONTAINS"),
        ("doc-0000320193-24-000076", "0000320193-24-000076/Item7", "CONTAINS"),
        ("0000320193-24-000123/Item7", "chunk-xbrl-net-sales-fy2024", "CONTAINS"),
        ("0000320193-24-000123/Item7", "chunk-item7-p1", "CONTAINS"),
        ("0000320193-24-000123/Item1A", "chunk-item1a-p1", "CONTAINS"),
        ("0000320193-24-000076/Item7", "chunk-item7-old-p1", "CONTAINS"),
        ("chunk-xbrl-net-sales-fy2024", "chunk-item7-p1", "NEXT"),
        ("chunk-item7-old-p1", "chunk-item7-p1", "REFERENCES"),
        ("doc-0000320193-24-000123", "doc-0000320193-24-000076", "TEMPORAL_TRANSITION"),
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


def write_eval_context(output_dir: Path, questions: list[dict]) -> None:
    lines = [
        "# Evaluation paths in this graph",
        "",
        "This demo graph mirrors three accepted custom-judge items used in CI:",
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
        labels = row.get("relevant_chunk_ids") or []
        if not labels and row.get("ground_truth", {}).get("relevant_chunk_ids"):
            labels = row["ground_truth"]["relevant_chunk_ids"]
        lines.append("")
        lines.append("---")
        lines.append("")
    (output_dir / "eval_context.md").write_text("\n".join(lines), encoding="utf-8")


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


def render_styled_visualization(graph: nx.DiGraph, output_path: Path) -> Path:
    """Write a blog-friendly Cytoscape HTML with readable fonts and type colors."""
    elements = _graph_to_cytoscape_elements(graph)
    elements_json = json.dumps(elements, indent=2, ensure_ascii=False)

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
    header {{
      padding: 0.75rem 1rem;
      background: #fff;
      border-bottom: 1px solid #cbd5e1;
      font-size: 0.875rem;
    }}
    header h1 {{
      margin: 0 0 0.25rem;
      font-size: 1rem;
      font-weight: 600;
    }}
    header p {{ margin: 0; color: #475569; font-size: 0.8125rem; }}
    #cy {{ width: 100%; height: calc(100vh - 56px); background: #f8fafc; }}
    #legend {{
      position: absolute;
      top: 64px;
      right: 12px;
      background: rgba(255, 255, 255, 0.95);
      border: 1px solid #cbd5e1;
      border-radius: 6px;
      padding: 0.5rem 0.65rem;
      font-size: 0.6875rem;
      line-height: 1.5;
      box-shadow: 0 1px 3px rgba(15, 23, 42, 0.08);
    }}
    #legend strong {{ display: block; margin-bottom: 0.25rem; font-size: 0.75rem; }}
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
      max-width: 280px;
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
  <header>
    <h1>Apple (AAPL) disclosure graph — evaluation paths</h1>
    <p>Hover nodes for details · drag to pan · scroll to zoom</p>
  </header>
  <div id="legend">
    <strong>Node types</strong>
    <div><span class="swatch" style="background:#bfdbfe;border-color:#2563eb"></span>Document</div>
    <div><span class="swatch" style="background:#a5f3fc;border-color:#0891b2"></span>Section</div>
    <div><span class="swatch" style="background:#bbf7d0;border-color:#16a34a"></span>XBRL fact</div>
    <div><span class="swatch" style="background:#e9d5ff;border-color:#9333ea"></span>HTML chunk</div>
    <div><span class="swatch" style="background:#fde68a;border-color:#ca8a04"></span>XBRL narrative</div>
  </div>
  <div id="tooltip"></div>
  <div id="cy"></div>
  <script>
    const graphElements = {elements_json};
    cytoscape.use(cytoscapeDagre);

    const cy = cytoscape({{
      container: document.getElementById('cy'),
      elements: [...graphElements.nodes, ...graphElements.edges],
      minZoom: 0.4,
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
          selector: 'edge',
          style: {{
            'width': 1.5,
            'line-color': '#64748b',
            'target-arrow-color': '#64748b',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'label': 'data(label)',
            'font-size': '7px',
            'color': '#334155',
            'text-background-color': '#f8fafc',
            'text-background-opacity': 0.85,
            'text-background-padding': '2px',
            'text-rotation': 'autorotate',
          }},
        }},
        {{
          selector: 'edge[edge_type = "TEMPORAL_TRANSITION"]',
          style: {{
            'line-color': '#dc2626',
            'target-arrow-color': '#dc2626',
            'line-style': 'dashed',
          }},
        }},
        {{
          selector: 'node:selected',
          style: {{ 'border-width': 3, 'border-color': '#0f172a' }},
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

    const tooltip = document.getElementById('tooltip');
    cy.on('mouseover', 'node', (evt) => {{
      const d = evt.target.data();
      const lines = [
        `<strong>${{d.label || d.id}}</strong>`,
        d.node_type ? `Type: ${{d.node_type}}` : null,
        d.prop_text ? d.prop_text : null,
        d.prop_xbrl_concept ? `Concept: ${{d.prop_xbrl_concept}}` : null,
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

    graph = build_eval_demo_graph()
    export_graphml(graph, output_dir / "eval_demo.graphml")

    html_path = render_styled_visualization(graph, output_dir / "visualization.html")

    report_path = output_dir / "report.md"
    ReportGenerator().visualize(graph, report_path, source_model_count=2, include_samples=True)

    metadata = calculate_graph_stats(graph, source_model_count=2)
    stats_path = output_dir / "graph_stats.json"
    stats_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    write_eval_context(output_dir, load_eval_questions())

    print(f"Wrote {html_path}")
    print(f"Wrote {report_path}")
    print(f"Wrote {stats_path}")
    print(f"Nodes: {metadata.node_count}, edges: {metadata.edge_count}")


if __name__ == "__main__":
    main()
