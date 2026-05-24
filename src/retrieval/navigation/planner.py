"""LLM / mock hop proposal planner (009)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage

from graph.edge_catalog import STRUCTURAL_EDGE_TYPES
from models.enums import GraphEdgeType
from models.graph import GraphNode
from retrieval.macro.llm_json import extract_json_from_llm
from retrieval.navigation.models import (
    HopCandidate,
    HopDirection,
    HopProposal,
    NavigationStage,
    ProposalSource,
)
from retrieval.orchestration.llm import create_chat_llm
from tracing.console_trace.llm import traced_llm_invoke


def _fixture_dir() -> Path:
    return Path("tests/fixtures/navigation_planner")


def _tokenize(query: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", query.lower()) if len(t) > 2}


def _score_node(query_tokens: set[str], node: GraphNode) -> float:
    text = f"{node.label} {node.node_id} {node.source_ref}".lower()
    hits = sum(1 for t in query_tokens if t in text)
    return float(hits)


def _neighbor_candidates(
    graph_api,
    snapshot_id: str,
    source_node_id: str,
    query: str,
    max_n: int,
) -> list[HopCandidate]:
    edges = graph_api.outgoing_edges(
        snapshot_id, source_node_id, list(STRUCTURAL_EDGE_TYPES)
    )
    tokens = _tokenize(query)
    ranked: list[tuple[float, HopCandidate]] = []
    for edge_type, target in edges:
        score = _score_node(tokens, target)
        ranked.append(
            (
                score,
                HopCandidate(
                    target_node_id=target.node_id,
                    edge_type=edge_type,
                    direction=HopDirection.OUTGOING,
                    score=score,
                ),
            )
        )
    ranked.sort(key=lambda x: (-x[0], x[1].target_node_id))
    return [c for _, c in ranked[:max_n]]


def _load_mock_fixture(stage: str, query: str) -> HopProposal | None:
    q = query.lower()
    name = None
    if "footnote" in q or "accounting" in q:
        name = "footnote_chain"
    elif "revenue" in q or "prior quarter" in q:
        name = "revenue_xbrl"
    elif "risk" in q or "md&a" in q or "mda" in q:
        name = "mda_risk"
    if not name:
        return None
    path = _fixture_dir() / stage / f"{name}.json"
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    data["stage"] = stage
    return HopProposal.model_validate(data)


def propose_next_hop(
    *,
    stage: NavigationStage,
    query: str,
    snapshot_id: str,
    source_node_id: str,
    graph_api,
    prior_visits: list,
    filing_set: list,
    max_candidates: int = 3,
) -> HopProposal:
    if os.environ.get("USE_MOCK_LLM", "0") == "1":
        mock = _load_mock_fixture(stage.value, query)
        if mock is not None and mock.source_node_id == source_node_id:
            return mock.model_copy(update={"proposal_source": ProposalSource.MOCK})
        cands = _neighbor_candidates(graph_api, snapshot_id, source_node_id, query, max_candidates)
        return HopProposal(
            stage=stage,
            source_node_id=source_node_id,
            candidates=cands,
            intent_note="mock neighbor rank",
            proposal_source=ProposalSource.MOCK,
        )

    edges = graph_api.outgoing_edges(
        snapshot_id, source_node_id, list(STRUCTURAL_EDGE_TYPES)
    )
    summary = [
        {
            "target_node_id": t.node_id,
            "label": t.label[:120],
            "edge_type": et.value,
        }
        for et, t in edges[:12]
    ]
    system = (
        "You propose the next graph hop for SEC filing navigation. "
        "Return JSON only: "
        '{"candidates":[{"target_node_id":"...","edge_type":"CONTAINS|NEXT|FOOTNOTE_OF|REFERENCES",'
        '"direction":"outgoing","score":0.0}],"intent_note":"..."}'
    )
    human = json.dumps(
        {
            "stage": stage.value,
            "query": query,
            "source_node_id": source_node_id,
            "neighbors": summary,
        }
    )
    llm = create_chat_llm(temperature=0)
    resp, _trace_patch = traced_llm_invoke(
        f"navigation_{stage.value}",
        llm,
        [SystemMessage(content=system), HumanMessage(content=human)],
    )
    data = extract_json_from_llm(resp.content or "")
    raw_cands = data.get("candidates") or []
    candidates: list[HopCandidate] = []
    for item in raw_cands[:max_candidates]:
        if not isinstance(item, dict):
            continue
        try:
            et = GraphEdgeType(str(item.get("edge_type", "CONTAINS")))
        except ValueError:
            continue
        candidates.append(
            HopCandidate(
                target_node_id=str(item.get("target_node_id", "")),
                edge_type=et,
                direction=HopDirection.OUTGOING,
                score=float(item.get("score", 0)),
            )
        )
    if not candidates:
        candidates = _neighbor_candidates(
            graph_api, snapshot_id, source_node_id, query, max_candidates
        )
    return HopProposal(
        stage=stage,
        source_node_id=source_node_id,
        candidates=candidates,
        intent_note=str(data.get("intent_note", "")),
        proposal_source=ProposalSource.LLM,
    )
