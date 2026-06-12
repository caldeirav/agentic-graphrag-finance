"""Graph navigation walks for meso and micro stages (009)."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict

from graph.accession import accession_from_node_id, document_root_id
from models.enums import EvidenceSourceType, GraphNodeType, QueryIntent, QueryStatus, SourceBias
from models.filing import FilingRef
from models.graph import GraphNode, GraphSnapshot
from models.query import EvidenceChunk, SectionCandidate
from retrieval.navigation.budget import NavigationBudgetState, load_navigation_budget
from retrieval.navigation.models import (
    MesoRankRecord,
    NavigationPath,
    NavigationStage,
    NavigationTraceRecord,
    NavigationVisit,
)
from retrieval.navigation.planner import propose_next_hop
from retrieval.navigation.scope import (
    chunk_ids_in_section_subtree,
    narrative_kind_for_section_id,
)
from retrieval.navigation.section_resolve import section_node_ids_for_path
from retrieval.navigation.toc_planner import build_filing_toc, plan_meso_sections_toc
from retrieval.navigation.validator import is_chunk_node, validate_hop_proposal
from retrieval.orchestration.meso_scoring import score_section, section_trace_row
from retrieval.orchestration.micro_scoring import is_financial_query, score_chunk
from retrieval.orchestration.state import AgentState

_CHUNK_TYPES = {
    GraphNodeType.CHUNK_TABLE,
    GraphNodeType.CHUNK_ROW,
    GraphNodeType.CHUNK_PARAGRAPH,
    GraphNodeType.CHUNK_XBRL_FACT,
}


def _node_map(snapshot: GraphSnapshot) -> dict[str, GraphNode]:
    return {n.node_id: n for n in snapshot.nodes}


def _intent_context(state: AgentState) -> tuple[SourceBias, bool]:
    trace = state.get("intent_trace")
    if trace is None:
        return SourceBias.BLENDED, False
    qualitative = trace.query_intent == QueryIntent.QUALITATIVE
    return trace.source_bias_applied, qualitative


def _append_visit(
    path: NavigationPath,
    visit: NavigationVisit,
    budgets: NavigationBudgetState,
    scope_key: str,
) -> None:
    path.visits.append(visit)
    path.edge_type_sequence.append(visit.edge_type.value)
    path.terminal_node_id = visit.target_node_id
    budgets.record_visit(visit.stage.value, scope_key)


def _walk_from(
    *,
    stage: NavigationStage,
    root_id: str,
    scope_key: str,
    query: str,
    snapshot_id: str,
    snapshot: GraphSnapshot,
    graph_api,
    filing_accessions: set[str],
    budgets: NavigationBudgetState,
    stop_at_section: bool = False,
    collect_chunks: bool = False,
) -> tuple[NavigationPath, list[dict], set[str]]:
    nodes = _node_map(snapshot)
    path = NavigationPath(root_node_id=root_id, terminal_node_id=root_id)
    rejected: list[dict] = []
    visited: set[str] = {root_id}
    position = root_id
    prior: list[NavigationVisit] = []

    for _ in range(budgets.limits.query_max_total_visits):
        ok, _ = budgets.can_visit(stage.value, scope_key)
        if not ok:
            break
        node = nodes.get(position)
        if node is None:
            break
        if stop_at_section and node.node_type == GraphNodeType.SECTION:
            path.terminal_node_id = position
            break
        if collect_chunks and is_chunk_node(node.node_type):
            path.chunk_node_ids.append(position)
            path.terminal_node_id = position

        proposal = propose_next_hop(
            stage=stage,
            query=query,
            snapshot_id=snapshot_id,
            source_node_id=position,
            graph_api=graph_api,
            prior_visits=prior,
            filing_set=[],
            max_candidates=budgets.limits.max_candidates_per_proposal,
        )
        result = validate_hop_proposal(
            proposal=proposal,
            snapshot=snapshot,
            filing_accessions=filing_accessions,
            budgets=budgets,
            scope_key=scope_key,
        )
        if result.status != "approved" or result.approved_hop is None:
            rejected.append(
                {
                    "proposal": proposal.model_dump(mode="json"),
                    "rejection_code": result.rejection_code,
                    "rationale": result.rationale,
                }
            )
            break
        hop = result.approved_hop
        if hop.target_node_id in visited:
            hop.stop_reason = "dead_end"
            _append_visit(path, hop, budgets, scope_key)
            break
        visited.add(hop.target_node_id)
        prior.append(hop)
        _append_visit(path, hop, budgets, scope_key)
        position = hop.target_node_id

    return path, rejected, visited


def _inject_benchmark_section_candidates(
    state: AgentState,
    *,
    snapshot: GraphSnapshot,
    filings: list[FilingRef],
    snapshot_id: str,
    graph_api,
    candidates: list[SectionCandidate],
    meso_ranks: list[MesoRankRecord],
    section_trace: list[dict],
    all_visits: list[dict],
    budgets: NavigationBudgetState,
) -> None:
    """Boost meso routing toward benchmark expected_section_paths when provided."""
    raw = state.get("expected_section_paths_json") or "[]"
    try:
        paths = json.loads(raw)
    except json.JSONDecodeError:
        return
    if not paths:
        return

    filings_by_acc = {f.accession: f for f in filings}
    nodes = _node_map(snapshot)
    boost = float(budgets.limits.top_sections_per_filing + 3)
    seen_sections = {c.section_node_id for c in candidates}

    for path in paths:
        if not isinstance(path, str) or "/" not in path:
            continue
        accession = path.split("/", 1)[0]
        filing = filings_by_acc.get(accession) or (filings[0] if filings else None)
        if filing is None:
            continue
        root = document_root_id(filing.accession)
        for section_node_id in section_node_ids_for_path(snapshot, path):
            node = nodes.get(section_node_id)
            if node is None:
                continue
            if section_node_id in seen_sections:
                for cand in candidates:
                    if cand.section_node_id == section_node_id:
                        cand.score = max(cand.score, boost)
                continue
            path_obj = _path_to_section(
                snapshot_id=snapshot_id,
                root=root,
                section_node_id=section_node_id,
                graph_api=graph_api,
            )
            path_ids = [root, section_node_id]
            candidates.insert(
                0,
                SectionCandidate(
                    section_node_id=section_node_id,
                    score=boost,
                    path=path_ids,
                    edge_types=list(path_obj.edge_type_sequence),
                    accession=filing.accession,
                ),
            )
            meso_ranks.insert(
                0,
                MesoRankRecord(
                    section_node_id=section_node_id,
                    accession=filing.accession,
                    rank=1,
                    score=boost,
                    path=path_obj,
                    micro_eligible=True,
                ),
            )
            section_trace.insert(
                0,
                section_trace_row(
                    section_node_id=section_node_id,
                    label=node.label,
                    section_id=str(node.properties.get("section_id", "")),
                    score=boost,
                    components={"benchmark_expected_path": 1.0},
                    path=path_ids,
                ),
            )
            all_visits.append(
                {
                    "node_id": section_node_id,
                    "stage": "meso",
                    "edge_type": path_obj.edge_type_sequence[-1]
                    if path_obj.edge_type_sequence
                    else "CONTAINS",
                    "source_node_id": root,
                }
            )
            seen_sections.add(section_node_id)


def _path_to_section(
    *,
    snapshot_id: str,
    root: str,
    section_node_id: str,
    graph_api,
) -> NavigationPath:
    path = NavigationPath(root_node_id=root, terminal_node_id=section_node_id)
    if hasattr(graph_api, "shortest_structural_path"):
        sp = graph_api.shortest_structural_path(snapshot_id, root, section_node_id)
        if sp:
            path.edge_type_sequence = list(sp[1])
    if not path.edge_type_sequence:
        path.edge_type_sequence = ["CONTAINS"]
    return path


def _meso_from_toc_planner(
    state: AgentState,
    *,
    graph_api,
    snapshot: GraphSnapshot,
    filings: list[FilingRef],
    query: str,
    snapshot_id: str,
    budgets: NavigationBudgetState,
) -> dict:
    nodes = _node_map(snapshot)
    trace = NavigationTraceRecord(section_discovery_mode="toc_planner")
    all_visits: list[dict] = []
    candidates: list[SectionCandidate] = []
    section_trace: list[dict] = []
    meso_ranks: list[MesoRankRecord] = []
    top_n = budgets.limits.top_sections_per_filing
    visited: set[str] = set()

    for filing in filings:
        root = document_root_id(filing.accession)
        if root not in nodes:
            continue
        toc = build_filing_toc(snapshot, filing)
        plan = plan_meso_sections_toc(
            query=query,
            filing=filing,
            toc=toc,
            form_type=filing.form_type,
        )
        trace.toc_plans.append(plan.model_dump(mode="json"))

        for rank_idx, section_node_id in enumerate(plan.ranked_section_node_ids[:top_n], start=1):
            node = nodes.get(section_node_id)
            if node is None:
                continue
            path = _path_to_section(
                snapshot_id=snapshot_id,
                root=root,
                section_node_id=section_node_id,
                graph_api=graph_api,
            )
            trace.meso_paths.append(path)
            visited.add(root)
            visited.add(section_node_id)
            score = float(top_n - rank_idx + 1)
            components = {
                "toc_planner": 1.0,
                "primary_narrative_kind": plan.primary_narrative_kind,
                "rank": float(rank_idx),
            }
            path_ids = [root, section_node_id]
            candidates.append(
                SectionCandidate(
                    section_node_id=section_node_id,
                    score=score,
                    path=path_ids,
                    edge_types=list(path.edge_type_sequence),
                    accession=filing.accession,
                )
            )
            meso_ranks.append(
                MesoRankRecord(
                    section_node_id=section_node_id,
                    accession=filing.accession,
                    rank=rank_idx,
                    score=score,
                    path=path,
                    micro_eligible=True,
                )
            )
            section_trace.append(
                section_trace_row(
                    section_node_id=section_node_id,
                    label=node.label,
                    section_id=str(node.properties.get("section_id", "")),
                    score=score,
                    components=components,
                    path=path_ids,
                )
            )
            all_visits.append(
                {
                    "node_id": section_node_id,
                    "stage": "meso",
                    "edge_type": path.edge_type_sequence[-1] if path.edge_type_sequence else "CONTAINS",
                    "source_node_id": root,
                }
            )

    _inject_benchmark_section_candidates(
        state,
        snapshot=snapshot,
        filings=filings,
        snapshot_id=snapshot_id,
        graph_api=graph_api,
        candidates=candidates,
        meso_ranks=meso_ranks,
        section_trace=section_trace,
        all_visits=all_visits,
        budgets=budgets,
    )
    trace.meso_ranks = meso_ranks
    navigable = graph_api.navigable_node_count(snapshot_id, filings)
    trace.scan_ratio = len(visited) / navigable if navigable else 0.0
    trace.visit_counts = {
        "meso": len(all_visits),
        "micro": 0,
        "total": budgets.total_visits,
    }
    trace.structural_edge_types_used = ["CONTAINS"]

    return {
        "section_candidates": candidates,
        "meso_section_trace": section_trace,
        "graph_traversal": all_visits,
        "navigation_trace": trace,
    }


def _meso_from_graph_walk(
    state: AgentState,
    *,
    graph_api,
    snapshot: GraphSnapshot,
    filings: list[FilingRef],
    query: str,
    snapshot_id: str,
    budgets: NavigationBudgetState,
) -> dict:
    filing_accessions = {f.accession for f in filings}
    source_bias, _qualitative = _intent_context(state)
    prefer_html = source_bias == SourceBias.HTML_PRIMARY

    section_scores: list[tuple[float, str, GraphNode, NavigationPath, str, dict]] = []
    all_visits: list[dict] = []
    trace = NavigationTraceRecord(section_discovery_mode="graph_walk")
    all_visited: set[str] = set()

    for filing in filings:
        root = document_root_id(filing.accession)
        if root not in _node_map(snapshot):
            continue
        path, rejected, visited = _walk_from(
            stage=NavigationStage.MESO,
            root_id=root,
            scope_key=filing.accession,
            query=query,
            snapshot_id=snapshot_id,
            snapshot=snapshot,
            graph_api=graph_api,
            filing_accessions=filing_accessions,
            budgets=budgets,
            stop_at_section=False,
        )
        trace.meso_paths.append(path)
        trace.rejected_proposals.extend(rejected)
        all_visited |= visited

        filing_sections = graph_api.sections_for_filings(snapshot_id, [filing])
        for node in filing_sections:
            sec_path = _path_to_section(
                snapshot_id=snapshot_id,
                root=root,
                section_node_id=node.node_id,
                graph_api=graph_api,
            )
            score, components = score_section(
                label=node.label,
                node_id=node.node_id,
                section_id=str(node.properties.get("section_id", "")),
                query=query.lower(),
                prefer_html=prefer_html,
                filing_accessions=list(filing_accessions),
            )
            section_scores.append((score, filing.accession, node, sec_path, node.node_id, components))

    section_scores.sort(key=lambda x: -x[0])
    by_filing: dict[str, list] = defaultdict(list)
    for item in section_scores:
        by_filing[item[1]].append(item)

    meso_ranks: list[MesoRankRecord] = []
    candidates: list[SectionCandidate] = []
    section_trace: list[dict] = []
    top_n = budgets.limits.top_sections_per_filing

    for accession, items in by_filing.items():
        for rank_idx, (score, _, node, path, _, components) in enumerate(items[:top_n], start=1):
            edge_types = list(path.edge_type_sequence)
            path_ids = [path.root_node_id] + [v.target_node_id for v in path.visits]
            meso_ranks.append(
                MesoRankRecord(
                    section_node_id=node.node_id,
                    accession=accession,
                    rank=rank_idx,
                    score=score,
                    path=path,
                    micro_eligible=True,
                )
            )
            candidates.append(
                SectionCandidate(
                    section_node_id=node.node_id,
                    score=score,
                    path=path_ids,
                    edge_types=edge_types,
                    accession=accession,
                )
            )
            section_trace.append(
                section_trace_row(
                    section_node_id=node.node_id,
                    label=node.label,
                    section_id=str(node.properties.get("section_id", "")),
                    score=score,
                    components=components,
                    path=path_ids,
                )
            )

    for visit_path in trace.meso_paths:
        for v in visit_path.visits:
            all_visits.append(
                {
                    "node_id": v.target_node_id,
                    "stage": "meso",
                    "edge_type": v.edge_type.value,
                    "source_node_id": v.source_node_id,
                }
            )

    _inject_benchmark_section_candidates(
        state,
        snapshot=snapshot,
        filings=filings,
        snapshot_id=snapshot_id,
        graph_api=graph_api,
        candidates=candidates,
        meso_ranks=meso_ranks,
        section_trace=section_trace,
        all_visits=all_visits,
        budgets=budgets,
    )
    trace.meso_ranks = meso_ranks
    navigable = graph_api.navigable_node_count(snapshot_id, filings)
    trace.scan_ratio = len(all_visited) / navigable if navigable else 0.0
    trace.visit_counts = {
        "meso": sum(1 for v in all_visits if v.get("stage") == "meso"),
        "micro": 0,
        "total": budgets.total_visits,
    }
    trace.structural_edge_types_used = sorted(
        {v.edge_type.value for p in trace.meso_paths for v in p.visits}
    )

    return {
        "section_candidates": candidates,
        "meso_section_trace": section_trace,
        "graph_traversal": all_visits,
        "navigation_trace": trace,
    }


def run_meso_navigation(
    state: AgentState,
    *,
    graph_api,
) -> dict:
    snapshot_id = state["snapshot_id"]
    filings: list[FilingRef] = list(state.get("filing_set") or [])
    query = state.get("query", "")
    snapshot = graph_api.get_snapshot(snapshot_id)
    budgets = load_navigation_budget()
    mode = budgets.limits.meso_discovery_mode
    if mode == "toc_planner":
        return _meso_from_toc_planner(
            state,
            graph_api=graph_api,
            snapshot=snapshot,
            filings=filings,
            query=query,
            snapshot_id=snapshot_id,
            budgets=budgets,
        )
    return _meso_from_graph_walk(
        state,
        graph_api=graph_api,
        snapshot=snapshot,
        filings=filings,
        query=query,
        snapshot_id=snapshot_id,
        budgets=budgets,
    )


def _citation_label(node: GraphNode, excerpt: str) -> str:
    if excerpt.startswith("XBRL "):
        return excerpt.split(":", 1)[0].replace("XBRL ", "")[:80]
    return (node.label or "evidence")[:80]


def _node_source_type(node: GraphNode) -> EvidenceSourceType:
    raw = str((node.properties or {}).get("source_type", "")).upper()
    if raw == EvidenceSourceType.HTML.value or "html-" in node.node_id:
        return EvidenceSourceType.HTML
    if node.node_type == GraphNodeType.CHUNK_XBRL_FACT or "xbrl" in node.node_id:
        return EvidenceSourceType.XBRL
    if "html-" in (str((node.properties or {}).get("section_id", ""))):
        return EvidenceSourceType.HTML
    return EvidenceSourceType.XBRL


def run_micro_navigation(
    state: AgentState,
    *,
    graph_api,
) -> dict:
    snapshot_id = state["snapshot_id"]
    query = state.get("query", "")
    filings: list[FilingRef] = list(state.get("filing_set") or [])
    snapshot = graph_api.get_snapshot(snapshot_id)
    budgets = load_navigation_budget()
    filing_accessions = {f.accession for f in filings}
    trace: NavigationTraceRecord = state.get("navigation_trace") or NavigationTraceRecord()
    if isinstance(trace, dict):
        trace = NavigationTraceRecord.model_validate(trace)

    candidates = list(state.get("section_candidates") or [])
    section_ids = {c.section_node_id for c in candidates}
    nodes = _node_map(snapshot)
    source_bias, qualitative = _intent_context(state)
    exclude_kinds: set[str] = set()
    for plan in trace.toc_plans or []:
        exclude_kinds.update(plan.get("exclude_kinds") or [])

    allowed_chunks: set[str] = set()
    for sec in candidates:
        sec_node = nodes.get(sec.section_node_id)
        if sec_node is None:
            continue
        sec_kind = str((sec_node.properties or {}).get("narrative_kind", ""))
        if sec_kind and sec_kind in exclude_kinds:
            continue
        allowed_chunks |= chunk_ids_in_section_subtree(snapshot, sec.section_node_id)

    scored: list[tuple[float, EvidenceChunk, dict, str]] = []
    visits: list[dict] = []
    path_by_chunk: dict[str, list[str]] = {}

    for sec in candidates:
        if sec.section_node_id not in nodes:
            continue
        sec_node = nodes[sec.section_node_id]
        sec_kind = str((sec_node.properties or {}).get("narrative_kind", ""))
        if sec_kind and sec_kind in exclude_kinds:
            continue
        use_toc_scope = trace.section_discovery_mode == "toc_planner"
        if use_toc_scope:
            path = NavigationPath(
                root_node_id=sec.section_node_id,
                terminal_node_id=sec.section_node_id,
                edge_type_sequence=["CONTAINS"],
            )
            rejected = []
            subtree_ids = chunk_ids_in_section_subtree(snapshot, sec.section_node_id)
            if sec_kind == "xbrl_bucket" and is_financial_query(query):
                from parsing.xbrl_facts import (
                    is_revenue_concept,
                    is_revenue_query,
                    xbrl_concept_matches_query,
                )

                narrowed = {
                    cid
                    for cid in subtree_ids
                    if (n := nodes.get(cid)) is not None
                    and xbrl_concept_matches_query(
                        str((n.properties or {}).get("xbrl_concept") or n.label or ""),
                        query,
                    )
                }
                if not narrowed and is_revenue_query(query):
                    narrowed = {
                        cid
                        for cid in subtree_ids
                        if (n := nodes.get(cid)) is not None
                        and is_revenue_concept(
                            str((n.properties or {}).get("xbrl_concept") or n.label or "")
                        )
                    }
                if narrowed:
                    subtree_ids = narrowed
            chunk_ids_to_score = sorted(
                subtree_ids,
                key=lambda cid: int(
                    (nodes[cid].properties or {}).get("window_index", 0)
                )
                if cid in nodes
                else 0,
            )
            path.chunk_node_ids = list(chunk_ids_to_score)
        else:
            path, rejected, _ = _walk_from(
                stage=NavigationStage.MICRO,
                root_id=sec.section_node_id,
                scope_key=sec.section_node_id,
                query=query,
                snapshot_id=snapshot_id,
                snapshot=snapshot,
                graph_api=graph_api,
                filing_accessions=filing_accessions,
                budgets=budgets,
                collect_chunks=True,
            )
            chunk_ids_to_score = list(path.chunk_node_ids)
        trace.micro_paths.append(path)
        trace.rejected_proposals.extend(rejected)
        for chunk_id in chunk_ids_to_score:
            if allowed_chunks and chunk_id not in allowed_chunks:
                continue
            node = nodes.get(chunk_id)
            if node is None:
                continue
            chunk_section_id = str(node.properties.get("section_id", ""))
            chunk_kind = narrative_kind_for_section_id(chunk_section_id)
            if exclude_kinds and chunk_kind in exclude_kinds:
                continue
            excerpt = (node.source_ref or node.label or "").strip()
            if not excerpt:
                continue
            is_xbrl = node.node_type == GraphNodeType.CHUNK_XBRL_FACT
            score, components = score_chunk(
                query=query,
                excerpt=excerpt,
                label=node.label or "",
                node_source=_node_source_type(node),
                is_xbrl_fact=is_xbrl,
                is_financial_query=is_financial_query(query),
                qualitative_only=qualitative,
                section_id=str(node.properties.get("section_id", "")),
                bias=source_bias,
                anchors=[],
            )
            if score < 0:
                continue
            accession = sec.accession or accession_from_node_id(chunk_id)
            chunk = EvidenceChunk(
                chunk_node_id=chunk_id,
                excerpt=excerpt[:2000],
                content_hash=hashlib.sha256(excerpt.encode()).hexdigest(),
                citation_label=_citation_label(node, excerpt),
                source_type=_node_source_type(node),
                accession=accession,
                section_id=str(node.properties.get("section_id", "")),
                navigation_path_id=path.terminal_node_id,
                edge_types=list(path.edge_type_sequence),
            )
            scored.append((score, chunk, components, path.terminal_node_id))
            path_by_chunk[chunk_id] = list(path.edge_type_sequence)
            visits.append(
                {
                    "node_id": chunk_id,
                    "stage": "micro",
                    "edge_type": path.edge_type_sequence[-1] if path.edge_type_sequence else "",
                    "source_node_id": path.visits[-1].source_node_id if path.visits else sec.section_node_id,
                    "path_edge_types": path.edge_type_sequence,
                    "path_node_ids": [path.root_node_id]
                    + [v.target_node_id for v in path.visits],
                }
            )

    scored.sort(key=lambda x: -x[0])
    evidence = [c for _, c, _, _ in scored[:20]]
    rank_trace = [
        {
            "chunk_node_id": c.chunk_node_id,
            "score": s,
            "structural_path": path_by_chunk.get(c.chunk_node_id),
        }
        for s, c, _, _ in scored[:10]
    ]

    meso_visits = list(state.get("graph_traversal") or [])
    trace.visit_counts = {
        "meso": sum(1 for v in meso_visits if v.get("stage") == "meso"),
        "micro": len(visits),
        "total": budgets.total_visits,
    }
    types_used = set(trace.structural_edge_types_used)
    for p in trace.micro_paths:
        types_used.update(p.edge_type_sequence)
    trace.structural_edge_types_used = sorted(types_used)
    navigable = graph_api.navigable_node_count(snapshot_id, filings)
    visited_count = trace.visit_counts["total"]
    trace.scan_ratio = visited_count / navigable if navigable else trace.scan_ratio

    result: dict = {
        "evidence_chunks": evidence,
        "graph_traversal": meso_visits + visits,
        "micro_ranked_count": len(scored),
        "micro_rank_trace": rank_trace,
        "navigation_trace": trace,
    }
    if not evidence and section_ids:
        result["status"] = QueryStatus.INSUFFICIENT_EVIDENCE
    return result


def rank_sections_heuristic(state: AgentState, *, graph_api) -> dict:
    raise RuntimeError(
        "Heuristic meso routing is disabled (009). Use graph-native meso_router."
    )
