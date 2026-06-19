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
from docling_graph.core.visualizers import InteractiveVisualizer, ReportGenerator

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
                "section_path": "0000320193-24-000123/Item7",
            },
        ),
        (
            "0000320193-24-000123/Item1A",
            {
                "node_type": "SECTION",
                "label": "Item 1A Risk Factors",
                "section_path": "0000320193-24-000123/Item1A",
            },
        ),
        (
            "0000320193-24-000076/Item7",
            {
                "node_type": "SECTION",
                "label": "Item 7 MD&A (prior year)",
                "section_path": "0000320193-24-000076/Item7",
            },
        ),
        (
            "chunk-xbrl-net-sales-fy2024",
            {
                "node_type": "CHUNK_XBRL_FACT",
                "label": "RevenueFromContractWithCustomerExcludingAssessedTax",
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

    visualizer = InteractiveVisualizer()
    html_path = visualizer.save_cytoscape_graph(
        graph,
        output_dir / "visualization.html",
        open_browser=False,
    )

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
