#!/usr/bin/env python3
"""Build an evaluation-path demo graph and render docling-graph visualizations.

Loads real GraphSnapshots from the published custom-judge v2 bundle (default v2.0.0),
selects three representative dev.jsonl items (financebench / finder / finagentbench),
extracts a readable subgraph with surrounding filing context, and renders an
interactive overlay with truncated materialized excerpts.

Uses docling-graph InteractiveVisualizer and ReportGenerator per:
https://github.com/docling-project/docling-graph/blob/main/docs/fundamentals/graph-management/visualization.md
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import networkx as nx
from docling_graph.core.utils.stats_calculator import calculate_graph_stats
from docling_graph.core.visualizers import ReportGenerator

from evaluation.generation.item_validator import load_graph_paths
from evaluation.reproduction.accession_index import AccessionIndex
from evaluation.reproduction.snapshot_loader import _merge_snapshots
from graph.store import load_snapshot
from models.enums import GraphEdgeType, GraphNodeType
from models.graph import GraphNode, GraphSnapshot
from retrieval.navigation.section_resolve import (
    chunk_ids_in_section_subtree,
    section_node_ids_for_path,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "assets" / "aapl-eval-graph"
DEFAULT_BUNDLE = REPO_ROOT / "data" / "benchmarks" / "custom-judge" / "v2.0.0"
VISUALIZATION_VERSION = "9"
MERGED_SNAPSHOT_ID = "blog-demo-v2"

# Representative paper-v2 dev items (XOM divestment + CAT/XOM compare; graph-full winners).
DEMO_ITEM_IDS = (
    "v2-financebench-0594",
    "v2-finder-0002",
    "v2-finagentbench-0095",
)

DEMO_SYNTHESIS_PATHS = {
    "v2-financebench-0594": "numeric_xbrl_deterministic",
    "v2-finder-0002": "live_llm",
    "v2-finagentbench-0095": "comparison_narrative_deterministic",
}

# XOM filing used by divestment items; prior doc on TEMPORAL_TRANSITION chain for demo.
XOM_PRIMARY_ACCESSION = "0000034088-26-000067"

CONTEXT_SECTION_MARKERS = (
    "item 1a",
    "item 7",
    "xbrl financial facts",
    "item 1.",
    "item 2.",
)

MAX_CONTEXT_NODES_PER_ACCESSION = 1
MAX_CITE_CHUNKS_PER_ITEM = 2

CHUNK_NODE_TYPES = frozenset(
    {
        GraphNodeType.CHUNK_PARAGRAPH,
        GraphNodeType.CHUNK_XBRL_FACT,
        GraphNodeType.CHUNK_TABLE,
        GraphNodeType.CHUNK_ROW,
    }
)

# Stable node-type palette (legend, cytoscape base styles, and overlays share these).
NODE_TYPE_COLORS: dict[str, tuple[str, str]] = {
    "DOCUMENT": ("#bfdbfe", "#2563eb"),
    "SECTION": ("#a5f3fc", "#0891b2"),
    "CHUNK_XBRL_FACT": ("#bbf7d0", "#16a34a"),
    "CHUNK_PARAGRAPH": ("#fde68a", "#ca8a04"),
    "CHUNK_TABLE": ("#ddd6fe", "#7c3aed"),
    "CHUNK_ROW": ("#fbcfe8", "#db2777"),
}


def truncate_excerpt(text: str, *, max_chars: int) -> tuple[str, bool]:
    cleaned = (text or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned, False
    return cleaned[:max_chars] + "…", True


def build_edgar_url(cik: str, accession: str) -> str:
    cik_int = str(cik).lstrip("0") or "0"
    acc_nodash = accession.replace("-", "")
    return (
        f"https://www.sec.gov/Archives/edgar/data/{cik_int}/"
        f"{acc_nodash}/{accession}-index.htm"
    )


def load_eval_questions(bundle_root: Path) -> list[dict]:
    path = bundle_root / "items" / "dev.jsonl"
    if not path.is_file():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def load_merged_demo_snapshot(bundle_root: Path, questions: list[dict]) -> GraphSnapshot:
    """Merge issuer snapshots required by the selected demo benchmark items."""
    index = AccessionIndex.build(bundle_root)
    accessions = sorted(collect_relevant_accessions(demo_questions(questions)))
    refs = index.resolve_accessions("blog-demo", accessions)
    snapshots = [
        load_snapshot(ref.ticker, ref.snapshot_id, index.graphs_dir) for ref in refs
    ]
    return _merge_snapshots(snapshots, MERGED_SNAPSHOT_ID)


def section_path_for_node(node: GraphNode) -> str:
    if node.properties.get("section_path"):
        return str(node.properties["section_path"])
    if node.node_type == GraphNodeType.SECTION and "/" in node.node_id:
        return node.node_id
    section_id = str(node.properties.get("section_id", ""))
    if section_id and node.node_id.startswith("doc-"):
        suffix = f"-{section_id}"
        if node.node_id.endswith(suffix):
            accession = node.node_id.removeprefix("doc-")[: -len(suffix)]
            return f"{accession}/{section_id}"
    return ""


def accession_from_section_path(section_path: str) -> str:
    if "/" not in section_path:
        return ""
    return section_path.split("/", 1)[0]


def primary_section_ids(snapshot: GraphSnapshot, section_path: str) -> list[str]:
    return section_node_ids_for_path(snapshot, section_path)


def context_section_paths(graph_paths: set[str], accession: str) -> list[str]:
    prefix = f"{accession}/"
    candidates = sorted(p for p in graph_paths if p.startswith(prefix))
    picked: list[str] = []
    seen: set[str] = set()
    for marker in CONTEXT_SECTION_MARKERS:
        for path in candidates:
            if marker in path.lower() and path not in seen:
                picked.append(path)
                seen.add(path)
                break
    return picked


def _keyword_tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z]{5,}", text.lower())}


def pick_cite_chunks(
    item: dict,
    snapshot: GraphSnapshot,
    *,
    limit: int = MAX_CITE_CHUNKS_PER_ITEM,
) -> list[str]:
    """Prefer relevant_chunk_ids that exist in the snapshot and match the question."""
    node_by_id = {n.node_id: n for n in snapshot.nodes}
    question_tokens = _keyword_tokens(item.get("question", ""))
    claims = (item.get("ground_truth") or {}).get("required_claims") or []
    claim_text = " ".join(claims)
    claim_tokens = _keyword_tokens(claim_text)

    ranked: list[tuple[int, str]] = []
    for chunk_id in item.get("relevant_chunk_ids") or []:
        node = node_by_id.get(chunk_id)
        if node is None or node.node_type not in CHUNK_NODE_TYPES:
            continue
        text = chunk_source_text(node).lower()
        if len(text) < 80:
            continue
        score = 0
        if "divest" in text:
            score += 12
        if "risk factor" in text or "geopolit" in text:
            score += 10
        if "singapore" in text or "argentina" in text:
            score += 8
        overlap = len(question_tokens & _keyword_tokens(text))
        score += overlap * 2
        score += len(claim_tokens & _keyword_tokens(text))
        ranked.append((score, chunk_id))

    if not ranked:
        for path in item.get("expected_section_paths") or []:
            for section_id in primary_section_ids(snapshot, path)[:1]:
                for chunk_id in sorted(chunk_ids_in_section_subtree(snapshot, section_id)):
                    node = node_by_id.get(chunk_id)
                    if node is not None:
                        ranked.append((0, chunk_id))
                    if len(ranked) >= limit:
                        break

    ranked.sort(key=lambda row: (-row[0], row[1]))
    accessions = list((item.get("expected_bindings") or {}).get("accessions") or [])
    if len(accessions) >= 2:
        per_accession = max(1, limit // len(accessions))
        out: list[str] = []
        for accession in accessions:
            acc_ranked = [row for row in ranked if accession in row[1]]
            for _, chunk_id in acc_ranked[:per_accession]:
                if chunk_id not in out:
                    out.append(chunk_id)
        if out:
            return out[:limit]

    out = []
    for _, chunk_id in ranked:
        if chunk_id not in out:
            out.append(chunk_id)
        if len(out) >= limit:
            break
    return out


def closure_to_documents(snapshot: GraphSnapshot, node_ids: set[str]) -> set[str]:
    """Expand selection upward along CONTAINS edges to filing documents."""
    expanded = set(node_ids)
    queue = list(node_ids)
    while queue:
        current = queue.pop()
        for edge in snapshot.edges:
            if edge.target_id != current or edge.edge_type != GraphEdgeType.CONTAINS:
                continue
            if edge.source_id not in expanded:
                expanded.add(edge.source_id)
                queue.append(edge.source_id)
    return expanded


def path_nodes_for_item(item: dict, snapshot: GraphSnapshot) -> set[str]:
    """Nodes on the evaluation path for one benchmark item."""
    ids: set[str] = set()
    for accession in (item.get("expected_bindings") or {}).get("accessions") or []:
        ids.add(doc_node_id(accession))
    for path in item.get("expected_section_paths") or []:
        ids.update(primary_section_ids(snapshot, path)[:1])
    ids.update(
        pick_cite_chunks(item, snapshot, limit=MAX_CITE_CHUNKS_PER_ITEM)
    )
    return closure_to_documents(snapshot, ids)


def pick_context_nodes(
    snapshot: GraphSnapshot,
    graph_paths: set[str],
    accessions: set[str],
    *,
    exclude: set[str],
) -> set[str]:
    """A few non-path section nodes to show filing structure (no chunk sprawl)."""
    context: set[str] = set()
    for accession in sorted(accessions):
        added = 0
        for path in context_section_paths(graph_paths, accession):
            if added >= MAX_CONTEXT_NODES_PER_ACCESSION:
                break
            for section_id in primary_section_ids(snapshot, path)[:1]:
                if section_id in exclude or section_id in context:
                    continue
                context.add(section_id)
                added += 1
                break
    return context


def demo_questions(all_questions: list[dict]) -> list[dict]:
    by_id = {row["item_id"]: row for row in all_questions}
    return [by_id[item_id] for item_id in DEMO_ITEM_IDS if item_id in by_id]


def collect_relevant_section_paths(questions: list[dict]) -> set[str]:
    paths: set[str] = set()
    for item in questions:
        paths.update(item.get("expected_section_paths") or [])
    return paths


def collect_relevant_accessions(questions: list[dict]) -> set[str]:
    accessions: set[str] = set()
    for item in questions:
        bindings = item.get("expected_bindings") or {}
        accessions.update(bindings.get("accessions") or [])
    return accessions


def doc_node_id(accession: str) -> str:
    return f"doc-{accession}"


def filing_ref_for_accession(snapshot: GraphSnapshot, accession: str):
    for ref in snapshot.manifest.filing_refs:
        if ref.accession == accession:
            return ref
    return None


def chunk_source_text(node: GraphNode) -> str:
    if node.source_ref:
        return node.source_ref
    if node.properties.get("text"):
        return str(node.properties["text"])
    return node.label or ""


def chunk_bindings(snapshot: GraphSnapshot, chunk_id: str) -> dict[str, str]:
    parent_ids = [
        edge.source_id
        for edge in snapshot.edges
        if edge.target_id == chunk_id and edge.edge_type == GraphEdgeType.CONTAINS
    ]
    section_path = ""
    for parent_id in parent_ids:
        parent = next((n for n in snapshot.nodes if n.node_id == parent_id), None)
        if parent is None:
            continue
        if parent.node_type == GraphNodeType.SECTION:
            section_path = section_path_for_node(parent) or parent.node_id
            break
    accession = accession_from_section_path(section_path)
    if not accession and parent_ids:
        parent_id = parent_ids[0]
        if parent_id.startswith("doc-"):
            accession = parent_id.removeprefix("doc-").rsplit("-", 1)[0]
    filing = filing_ref_for_accession(snapshot, accession) if accession else None
    return {
        "accession": accession,
        "form_type": filing.form_type if filing else "",
        "section_path": section_path,
        "cik": str(filing.cik if filing else ""),
    }


def chunk_materialized(
    node: GraphNode,
    *,
    bindings: dict[str, str],
    max_excerpt_chars: int,
) -> str:
    source = chunk_source_text(node)
    excerpt, truncated = truncate_excerpt(source, max_chars=max_excerpt_chars)
    payload = {
        "node_id": node.node_id,
        "node_type": node.node_type.value,
        "label": node.label,
        "source_ref": excerpt,
        "source_ref_truncated": truncated,
        "source_ref_total_chars": len(source),
        "properties": {k: str(v) for k, v in node.properties.items()},
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


def document_label(issuer: str, form_type: str, period_end: str) -> str:
    year = period_end[:4] if period_end else "????"
    return f"{issuer} {form_type} FY{year}"


def semantic_display_label(
    node: GraphNode,
    *,
    section_path: str = "",
    period_end: str = "",
    form_type: str = "10-K",
) -> str:
    """Short graph label — never the full chunk excerpt."""
    node_type = node.node_type.value
    if node_type == "DOCUMENT":
        year = period_end[:4] if period_end else "????"
        return f"FY{year}\n{form_type or '10-K'}"
    if node_type == "SECTION":
        item_number = str(node.properties.get("item_number", "")).strip()
        title = section_display_title(node)
        match = re.match(r"(Item\s+[\dA-Za-z.]+)\.?\s*(.*)", title, flags=re.I)
        if match:
            head, tail = match.groups()
            if tail.strip():
                return f"{head.strip()}\n{truncate_excerpt(tail.strip(), max_chars=16)[0]}"
            return head.strip()
        if item_number:
            return f"Item {item_number}"
        if section_path:
            tail = section_path.split("/", 1)[-1]
            if len(tail) > 18:
                return truncate_excerpt(tail, max_chars=18)[0].replace(" ", "\n", 1)
            return tail
        return "Section"
    if node_type == "CHUNK_XBRL_FACT":
        concept = str(node.properties.get("xbrl_concept") or node.label or "fact")
        short = concept.split(":")[-1].replace("_", " ")[:14]
        return f"XBRL\n{short}"
    if node_type == "CHUNK_PARAGRAPH":
        return "Paragraph\nchunk"
    if node_type == "CHUNK_TABLE":
        return "Table\nchunk"
    if node_type == "CHUNK_ROW":
        return "Table\nrow"
    return node_type.replace("CHUNK_", "").replace("_", " ").title()[:20]


def section_display_title(node: GraphNode) -> str:
    """Human-readable section title for panels (not graph excerpt labels)."""
    label = (node.label or "").strip()
    if re.match(r"Item\s+[\dA-Za-z]", label, flags=re.I) and len(label) <= 80:
        return label
    item_number = str(node.properties.get("item_number", "")).strip()
    kind_titles = {
        "risk_factors": "Risk Factors",
        "md_and_a": "Management's Discussion and Analysis",
        "business_description": "Business",
        "xbrl_financial_facts": "XBRL Financial Facts",
    }
    narrative_kind = str(node.properties.get("narrative_kind", ""))
    if item_number:
        tail = kind_titles.get(narrative_kind, "Section")
        return f"Item {item_number}. {tail}"
    if label and len(label) <= 80:
        return label
    return narrative_kind.replace("_", " ").title() or "Section"


def section_materialized(
    node: GraphNode,
    *,
    section_path: str,
    bindings: dict[str, str],
    child_node_count: int,
) -> str:
    title = section_display_title(node)
    payload = {
        "node_id": node.node_id,
        "node_type": "SECTION",
        "label": title,
        "section_path": section_path,
        "child_node_count": child_node_count,
        "properties": {k: str(v) for k, v in node.properties.items()},
        "bindings": bindings,
    }
    return json.dumps(payload, indent=2)


def section_bindings(snapshot: GraphSnapshot, section_path: str) -> dict[str, str]:
    accession = accession_from_section_path(section_path)
    filing = filing_ref_for_accession(snapshot, accession) if accession else None
    return {
        "accession": accession,
        "form_type": filing.form_type if filing else "",
        "section_path": section_path,
        "cik": str(filing.cik if filing else ""),
    }


def child_node_count(snapshot: GraphSnapshot, node_id: str) -> int:
    return sum(
        1
        for edge in snapshot.edges
        if edge.source_id == node_id and edge.edge_type == GraphEdgeType.CONTAINS
    )


def pick_temporal_demo_nodes(snapshot: GraphSnapshot, primary_accession: str) -> set[str]:
    """Prior filing document on the TEMPORAL_TRANSITION chain into the primary accession."""
    target_id = doc_node_id(primary_accession)
    extras: set[str] = {target_id}
    for edge in snapshot.edges:
        if (
            edge.edge_type == GraphEdgeType.TEMPORAL_TRANSITION
            and edge.target_id == target_id
        ):
            extras.add(edge.source_id)
    return extras


def eval_item_fields(item: dict) -> dict[str, object]:
    ground_truth = item.get("ground_truth") or {}
    return {
        "question_type_tag": item.get("question_type_tag"),
        "expected_answer": ground_truth.get("answer"),
        "expected_rubric": ground_truth.get("rubric"),
        "expected_bindings": item.get("expected_bindings") or {},
        "multi_filing_required": item.get("multi_filing_required"),
        "validation_status": item.get("validation_status"),
    }


def build_investigation_scenarios(
    questions: list[dict],
    snapshot: GraphSnapshot,
    graph_paths: set[str],
) -> list[dict]:
    """Demo investigation rows aligned with v2 bundle items and real graph node ids."""
    scenarios: list[dict] = []
    for item in demo_questions(questions):
        item_id = item["item_id"]
        section_paths = list(item.get("expected_section_paths") or [])
        path_ids = path_nodes_for_item(item, snapshot)
        accessions = list((item.get("expected_bindings") or {}).get("accessions") or [])
        cited = pick_cite_chunks(item, snapshot, limit=MAX_CITE_CHUNKS_PER_ITEM)
        visited = sorted(path_ids)
        highlight = sorted(path_ids)
        context_nodes = sorted(
            pick_context_nodes(
                snapshot,
                graph_paths,
                set(accessions),
                exclude=path_ids,
            )
        )

        edgar_links = []
        for accession in accessions:
            filing = filing_ref_for_accession(snapshot, accession)
            edgar_links.append(
                {
                    "accession": accession,
                    "form_type": filing.form_type if filing else "10-K",
                    "url": build_edgar_url(
                        str(filing.cik if filing else ""),
                        accession,
                    ),
                }
            )

        scenarios.append(
            {
                "scenario_id": item_id,
                **eval_item_fields(item),
                "inspiration_profile": item.get("inspiration_profile", "custom"),
                "question": item.get("question", ""),
                "expected_section_paths": section_paths,
                "visited_section_paths": section_paths,
                "cited_chunk_node_ids": cited,
                "synthesis_path": DEMO_SYNTHESIS_PATHS.get(item_id, "unknown"),
                "suggested_failure_class": None,
                "binding_miss": False,
                "highlight_nodes": highlight,
                "visited_nodes": visited,
                "cited_nodes": cited,
                "context_nodes": context_nodes,
                "missing_nodes": [],
                "edgar_links": edgar_links,
            }
        )
    return scenarios


def build_eval_demo_graph(
    snapshot: GraphSnapshot,
    questions: list[dict],
    graph_paths: set[str],
    *,
    max_excerpt_chars: int,
) -> tuple[nx.DiGraph, set[str], set[str]]:
    """Minimal subgraph: union of all item paths, temporal chain, and context sections."""
    demo_items = demo_questions(questions)
    accessions = collect_relevant_accessions(demo_items)

    path_ids: set[str] = set()
    for item in demo_items:
        path_ids |= path_nodes_for_item(item, snapshot)

    temporal_ids = pick_temporal_demo_nodes(snapshot, XOM_PRIMARY_ACCESSION)

    context_ids = pick_context_nodes(
        snapshot,
        graph_paths,
        accessions,
        exclude=path_ids | temporal_ids,
    )
    selected_ids = path_ids | temporal_ids | context_ids

    g = nx.DiGraph()
    node_by_id = {node.node_id: node for node in snapshot.nodes}

    for node_id in sorted(selected_ids):
        node = node_by_id.get(node_id)
        if node is None:
            continue
        if node_id in path_ids:
            demo_role = "path"
        elif node_id in temporal_ids and node_id not in path_ids:
            demo_role = "temporal"
        else:
            demo_role = "context"
        attrs = _graph_node_attrs(
            node,
            snapshot,
            max_excerpt_chars=max_excerpt_chars,
            graph_paths=graph_paths,
            demo_role=demo_role,
        )
        g.add_node(node_id, **attrs)

    for edge in snapshot.edges:
        if edge.source_id not in selected_ids or edge.target_id not in selected_ids:
            continue
        if edge.edge_type not in (
            GraphEdgeType.CONTAINS,
            GraphEdgeType.TEMPORAL_TRANSITION,
        ):
            continue
        g.add_edge(
            edge.source_id,
            edge.target_id,
            edge_type=edge.edge_type.value,
            label=edge.edge_type.value,
            edge_id=edge.edge_id,
        )

    return g, path_ids, context_ids | temporal_ids


def issuer_name_for_accession(graph_paths: set[str], accession: str) -> str:
    for path in sorted(graph_paths):
        if not path.startswith(f"{accession}/"):
            continue
        tail = path.split("/", 1)[1]
        match = re.search(
            r"(?:10-[KQ]|8-K)\s+(.+?)\s+\d{4}-\d{2}-\d{2}",
            tail,
            flags=re.IGNORECASE,
        )
        if match:
            return match.group(1).strip()
    return accession


def _graph_node_attrs(
    node: GraphNode,
    snapshot: GraphSnapshot,
    *,
    max_excerpt_chars: int,
    graph_paths: set[str],
    demo_role: str = "path",
) -> dict[str, object]:
    node_type = node.node_type.value
    source = chunk_source_text(node)
    excerpt, _ = truncate_excerpt(source, max_chars=120)
    section_path = section_path_for_node(node)
    attrs: dict[str, object] = {
        "node_type": node_type,
        "label": node.label or node.node_id,
        "demo_role": demo_role,
    }

    if section_path:
        attrs["section_path"] = section_path

    if node.node_type == GraphNodeType.DOCUMENT:
        accession = str(node.properties.get("accession", ""))
        filing = filing_ref_for_accession(snapshot, accession)
        period_end = str(
            node.properties.get("period_end", filing.period_end if filing else "")
        )
        form_type = str(node.properties.get("form_type", filing.form_type if filing else "10-K"))
        issuer = issuer_name_for_accession(graph_paths, accession)
        label = document_label(issuer, form_type, period_end)
        attrs["label"] = label
        attrs["display_label"] = semantic_display_label(
            node, period_end=period_end, form_type=form_type
        )
        attrs["accession"] = accession
        attrs["form_type"] = form_type
        attrs["period_end"] = period_end
        cik = str(filing.cik if filing else "")
        edgar_url = build_edgar_url(cik, accession) if cik else ""
        attrs["edgar_url"] = edgar_url
        attrs["materialized_json"] = document_materialized(
            node_id=node.node_id,
            label=label,
            accession=accession,
            form_type=form_type,
            period_end=period_end,
            cik=cik,
            edgar_url=edgar_url,
        )
        return attrs

    if node.node_type == GraphNodeType.SECTION:
        bindings = section_bindings(snapshot, section_path)
        attrs["display_label"] = semantic_display_label(node, section_path=section_path)
        attrs["materialized_json"] = section_materialized(
            node,
            section_path=section_path,
            bindings=bindings,
            child_node_count=child_node_count(snapshot, node.node_id),
        )
        return attrs

    attrs["display_label"] = semantic_display_label(node, section_path=section_path)

    if node.node_type in CHUNK_NODE_TYPES:
        attrs["prop_text"] = excerpt or node.label
        bindings = chunk_bindings(snapshot, node.node_id)
        if node.properties.get("source_type"):
            attrs["prop_sec_source"] = str(node.properties["source_type"])
        elif node.properties.get("sec_source"):
            attrs["prop_sec_source"] = str(node.properties["sec_source"])
        if node.properties.get("xbrl_concept"):
            attrs["prop_xbrl_concept"] = str(node.properties["xbrl_concept"])
        attrs["materialized_json"] = chunk_materialized(
            node,
            bindings=bindings,
            max_excerpt_chars=max_excerpt_chars,
        )

    return attrs


def write_eval_context(
    output_dir: Path,
    questions: list[dict],
    scenarios: list[dict],
    *,
    bundle_version: str,
) -> None:
    lines = [
        "# Evaluation paths in this graph",
        "",
        f"This demo graph is extracted from the custom-judge **{bundle_version}** bundle",
        "(merged XOM + CAT GraphSnapshots) for three representative `dev.jsonl` items.",
        "The graph shows the **union** of all three evaluation paths plus a XOM `TEMPORAL_TRANSITION`",
        "link between consecutive filings. Select an item to overlay path rings only — nodes stay visible.",
        "",
    ]
    for row in demo_questions(questions):
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
        "CHUNK_TABLE": "Table chunk",
        "CHUNK_ROW": "Table row",
    }
    rows = []
    for node_type, (bg, border) in NODE_TYPE_COLORS.items():
        if node_type not in labels:
            continue
        label = labels[node_type]
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
    max_excerpt_chars: int,
) -> Path:
    """Write blog-friendly Cytoscape HTML with investigation overlays."""
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
  <title>Paper v2 evaluation graph — agentic-graphrag-finance</title>
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
    .detail-note {{
      margin-top: 0.35rem;
      color: #64748b;
      font-size: 0.68rem;
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
      <h1>Investigation overlay</h1>
      <p>Select an evaluation item by id to highlight its path rings. The full union graph stays visible. Click <strong>document</strong>, <strong>section</strong>, or <strong>chunk</strong> nodes for materialized details.</p>
      <div id="scenario-buttons"></div>
      <div id="investigation-panel"></div>
    </aside>
    <div id="main">
      <header>
        <p>Custom-judge v2 disclosure graph (XOM + CAT) — union of three eval paths · TEMPORAL_TRANSITION between XOM filings · click nodes for details</p>
      </header>
      <div id="cy-wrap">
        <div id="legend">
          <strong>Overlay</strong>
          <div><span class="swatch" style="background:transparent;border-color:#16a34a;border-width:2px"></span>Expected ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#2563eb;border-width:2px"></span>Visited ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#ca8a04;border-width:2px"></span>Cited ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#dc2626;border-width:2px"></span>Missing ring</div>
          <div><span class="swatch" style="background:transparent;border-color:#64748b;border-width:2px;border-style:dashed"></span>Context (dimmed)</div>
          <div><span class="swatch" style="background:#fecaca;border-color:#dc2626"></span>Prior filing (temporal)</div>
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
    const maxExcerptChars = {max_excerpt_chars};
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
            'opacity': 1,
          }},
        }},
        {{
          selector: 'node[demo_role = "context"]',
          style: {{ 'opacity': 0.55, 'border-style': 'dashed' }},
        }},
        {{
          selector: 'node[demo_role = "temporal"]',
          style: {{ 'opacity': 0.85, 'border-style': 'dotted', 'border-color': '#dc2626' }},
        }},
        ...baseNodeStyles,
        {{
          selector: 'node[node_type = "DOCUMENT"], node[node_type = "SECTION"], node[node_type = "CHUNK_PARAGRAPH"], node[node_type = "CHUNK_XBRL_FACT"], node[node_type = "CHUNK_TABLE"], node[node_type = "CHUNK_ROW"]',
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
            'opacity': 0.65,
          }},
        }},
        {{
          selector: 'edge.overlay-active',
          style: {{ 'opacity': 1, 'line-color': '#64748b', 'target-arrow-color': '#64748b' }},
        }},
        {{
          selector: 'edge[edge_type = "TEMPORAL_TRANSITION"]',
          style: {{
            'line-color': '#dc2626',
            'target-arrow-color': '#dc2626',
            'line-style': 'dashed',
            'width': 2.5,
            'opacity': 1,
          }},
        }},
      ],
      layout: {{
        name: 'dagre',
        rankDir: 'TB',
        nodeSep: 48,
        rankSep: 64,
        edgeSep: 16,
        animate: false,
      }},
    }});

    cy.ready(() => {{
      cy.fit(undefined, 48);
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

    function renderSectionView(payload) {{
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
          <dt>section_path</dt><dd><code>${{escapeHtml(payload.section_path || '')}}</code></dd>
          <dt>child nodes</dt><dd>${{escapeHtml(String(payload.child_node_count ?? ''))}} direct CONTAINS children</dd>
        </dl>
        <h3 style="font-size:0.78rem;margin:0.75rem 0 0.25rem">properties</h3>
        <dl>${{propRows || '<dd><em>none</em></dd>'}}</dl>
        <h3 style="font-size:0.78rem;margin:0.75rem 0 0.25rem">bindings</h3>
        <dl>${{bindingRows || '<dd><em>none</em></dd>'}}</dl>`;
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
      const truncatedNote = payload.source_ref_truncated
        ? `<p class="detail-note">Excerpt truncated to ${{maxExcerptChars}} characters (${{payload.source_ref_total_chars}} in graph).</p>`
        : '';
      return `
        <dl>
          <dt>node_id</dt><dd><code>${{escapeHtml(payload.node_id || '')}}</code></dd>
          <dt>node_type</dt><dd><code>${{escapeHtml(payload.node_type || '')}}</code></dd>
          <dt>label</dt><dd>${{escapeHtml(payload.label || '')}}</dd>
          <dt>source_ref (excerpt)</dt>
          <dd><div class="detail-excerpt">${{escapeHtml(payload.source_ref || '')}}</div>${{truncatedNote}}</dd>
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
      detailTitle.textContent = nodeData.display_label || nodeData.label || nodeData.id;
      detailSubtitle.textContent = nodeData.node_type || '';
      if (payload.node_type === 'DOCUMENT') {{
        detailMaterialized.innerHTML = renderDocumentView(payload);
      }} else if (payload.node_type === 'SECTION') {{
        detailMaterialized.innerHTML = renderSectionView(payload);
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
      cy.nodes().removeClass(
        'overlay-expected overlay-visited overlay-cited overlay-missing'
      );
      cy.edges().removeClass('overlay-active');

      (scenario.highlight_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-expected'));
      (scenario.visited_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-visited'));
      (scenario.cited_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-cited'));
      (scenario.missing_nodes || []).forEach(id => cy.getElementById(id).addClass('overlay-missing'));
      cy.edges().forEach(edge => {{
        const src = edge.source().id();
        const tgt = edge.target().id();
        const active = (scenario.visited_nodes || []).includes(src)
          && (scenario.visited_nodes || []).includes(tgt);
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
    const clickableTypes = new Set([
      'DOCUMENT', 'SECTION', 'CHUNK_PARAGRAPH', 'CHUNK_XBRL_FACT', 'CHUNK_TABLE', 'CHUNK_ROW',
    ]);

    cy.on('mouseover', 'node', (evt) => {{
      const d = evt.target.data();
      const clickHint = clickableTypes.has(d.node_type) ? 'Click for node detail' : null;
      const lines = [
        `<strong>${{d.display_label || d.label || d.id}}</strong>`,
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
      if (clickableTypes.has(d.node_type)) {{
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
    parser.add_argument(
        "--bundle",
        type=Path,
        default=DEFAULT_BUNDLE,
        help="Custom-judge bundle root (must contain items/dev.jsonl and corpus/graphs/)",
    )
    parser.add_argument(
        "--max-excerpt-chars",
        type=int,
        default=1200,
        help="Maximum characters of source_ref shown in the materialized panel",
    )
    args = parser.parse_args()
    output_dir = args.output.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    bundle_root = args.bundle.resolve()

    questions = load_eval_questions(bundle_root)
    snapshot = load_merged_demo_snapshot(bundle_root, questions)
    graph_paths = load_graph_paths(bundle_root / "corpus" / "graph_node_index.json")
    bundle_version = json.loads((bundle_root / "manifest.json").read_text()).get(
        "version", bundle_root.name
    )

    scenarios = build_investigation_scenarios(questions, snapshot, graph_paths)
    graph, _path_ids, _context_ids = build_eval_demo_graph(
        snapshot,
        questions,
        graph_paths,
        max_excerpt_chars=args.max_excerpt_chars,
    )
    export_graphml(graph, output_dir / "eval_demo.graphml")

    html_path = render_styled_visualization(
        graph,
        output_dir / "visualization.html",
        scenarios=scenarios,
        max_excerpt_chars=args.max_excerpt_chars,
    )

    report_path = output_dir / "report.md"
    ReportGenerator().visualize(graph, report_path, source_model_count=2, include_samples=True)

    metadata = calculate_graph_stats(graph, source_model_count=2)
    stats_path = output_dir / "graph_stats.json"
    stats_path.write_text(
        json.dumps(metadata.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    write_eval_context(output_dir, questions, scenarios, bundle_version=bundle_version)
    write_investigation_overlay(output_dir, scenarios)

    index_html = output_dir / "index.html"
    index_html.write_text(
        f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=visualization.html?v={VISUALIZATION_VERSION}">
  <title>Paper v2 evaluation graph</title>
</head>
<body>
  <p><a href="visualization.html?v={VISUALIZATION_VERSION}">Open the interactive graph</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )

    print(f"Bundle: {bundle_root} ({bundle_version})")
    print(f"Wrote {html_path}")
    print(f"Wrote {report_path}")
    print(f"Wrote {stats_path}")
    print(f"Wrote {output_dir / 'investigation_overlay.json'}")
    print(f"Nodes: {metadata.node_count}, edges: {metadata.edge_count}")


if __name__ == "__main__":
    main()
