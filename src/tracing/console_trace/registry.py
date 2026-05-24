"""Ask-graph stage registry for console trace renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from retrieval.orchestration.state import AgentState
from tracing.console_trace.models import TraceEvent, TraceEventType, TraceRunConfig

StageRenderer = Callable[[str, AgentState, list[TraceEvent], TraceRunConfig], list[str]]


@dataclass(frozen=True)
class TraceStageRegistration:
    stage_id: str
    title: str
    order: int
    schema_version: int
    state_field_map: tuple[str, ...]
    renderer: StageRenderer


def _stage_end(events: list[TraceEvent]) -> TraceEvent | None:
    return next((e for e in events if e.event_type == TraceEventType.STAGE_END), None)


def _header_lines(stage_id: str, events: list[TraceEvent]) -> list[str]:
    end = _stage_end(events)
    lines = [f"[{stage_id}] {end.decision_summary if end else '—'}"]
    if end and end.duration_ms is not None:
        lines.append(f"  duration: {end.duration_ms} ms")
    return lines


def _append_llm_verbose(lines: list[str], events: list[TraceEvent]) -> None:
    for ev in events:
        if ev.event_type == TraceEventType.LLM_IO and ev.llm_io:
            lines.append(f"  llm: {ev.llm_io.model_id} ({ev.llm_io.latency_ms} ms)")
            for msg in ev.llm_io.messages_preview:
                lines.append(f"    {msg.get('role', '?')}: {msg.get('content', '')[:200]}")
            if ev.llm_io.response_preview:
                lines.append(f"    response: {ev.llm_io.response_preview[:300]}")


def _format_components(components: dict) -> str:
    if not components:
        return ""
    parts = [f"{k}={v}" for k, v in components.items()]
    return ", ".join(parts)


def _render_lines(
    stage_id: str,
    state: AgentState,
    events: list[TraceEvent],
    config: TraceRunConfig,
) -> list[str]:
    lines = _header_lines(stage_id, events)
    end = _stage_end(events)
    if end and end.payload:
        for key, val in end.payload.items():
            if val is None or val == "" or val == []:
                continue
            lines.append(f"  {key}: {val}")
    if config.verbose:
        _append_llm_verbose(lines, events)
    return lines


def _render_meso_router(
    stage_id: str,
    state: AgentState,
    events: list[TraceEvent],
    config: TraceRunConfig,
) -> list[str]:
    lines = _header_lines(stage_id, events)
    end = _stage_end(events)
    payload = (end.payload if end else {}) or {}
    if payload.get("candidate_count") is not None:
        lines.append(f"  candidate_count: {payload['candidate_count']}")
    if payload.get("navigation_mode"):
        lines.append(f"  navigation_mode: {payload['navigation_mode']}")
    if payload.get("edge_types_used"):
        lines.append(f"  edge_types_used: {payload['edge_types_used']}")
    if payload.get("sample_path"):
        lines.append(f"  sample_path: {payload['sample_path']}")
    if payload.get("visit_count"):
        lines.append(f"  visit_count: {payload['visit_count']}")
    if payload.get("rejected_count") is not None:
        lines.append(f"  rejected_count: {payload['rejected_count']}")
    if payload.get("top_section_ids"):
        lines.append(f"  top_section_ids: {payload['top_section_ids']}")
    for idx, sec in enumerate(payload.get("top_sections") or [], 1):
        label = sec.get("label") or sec.get("section_node_id", "")
        comps = _format_components(sec.get("components") or {})
        lines.append(
            f"  #{idx} score={sec.get('score')} label={label!r} section_id={sec.get('section_id', '')!r}"
        )
        if comps:
            lines.append(f"      components: {comps}")
    if config.verbose:
        _append_llm_verbose(lines, events)
    return lines


def _render_micro_extractor(
    stage_id: str,
    state: AgentState,
    events: list[TraceEvent],
    config: TraceRunConfig,
) -> list[str]:
    lines = _header_lines(stage_id, events)
    end = _stage_end(events)
    payload = (end.payload if end else {}) or {}
    if payload.get("navigation_mode"):
        lines.append(f"  navigation_mode: {payload['navigation_mode']}")
    if payload.get("edge_types_used"):
        lines.append(f"  edge_types_used: {payload['edge_types_used']}")
    if payload.get("sample_path"):
        lines.append(f"  sample_path: {payload['sample_path']}")
    if payload.get("visit_count"):
        lines.append(f"  visit_count: {payload['visit_count']}")
    if payload.get("rejected_count") is not None:
        lines.append(f"  rejected_count: {payload['rejected_count']}")
    for key in ("count_before", "count_after", "source_bias"):
        if payload.get(key) is not None:
            lines.append(f"  {key}: {payload[key]}")
    for idx, row in enumerate(payload.get("ranked") or [], 1):
        comps = _format_components(row.get("components") or {})
        cid = row.get("chunk_node_id", "")
        lines.append(
            f"  #{idx} score={row.get('score')} [{row.get('source_type')}] {cid}"
        )
        if comps:
            lines.append(f"      components: {comps}")
        preview = (row.get("excerpt_preview") or "")[:120]
        if preview:
            lines.append(f"      excerpt: {preview}")
    if config.verbose:
        from retrieval.orchestration.trace_payloads import (
            load_trace_config_limits,
            structural_paths_for_evidence,
        )

        limit = load_trace_config_limits()["top_structural_paths"]
        paths = structural_paths_for_evidence(state, limit=limit)
        if not paths:
            for row in (payload.get("ranked") or [])[:limit]:
                edges = row.get("structural_path_edges")
                if edges:
                    paths.append(
                        {
                            "chunk_node_id": row.get("chunk_node_id"),
                            "path_edge_types": edges,
                        }
                    )
        for path_row in paths[:limit]:
            edges = path_row.get("path_edge_types") or []
            lines.append(
                f"  path {path_row.get('chunk_node_id', '')}: "
                f"{' → '.join(str(e) for e in edges) or '(none)'}"
            )
        _append_llm_verbose(lines, events)
    return lines


ASK_TRACE_REGISTRY: dict[str, TraceStageRegistration] = {
    "macro_router": TraceStageRegistration(
        stage_id="macro_router",
        title="Macro router",
        order=1,
        schema_version=1,
        state_field_map=(
            "macro_plan",
            "filing_set",
            "macro_llm_skipped",
            "macro_binding_record",
        ),
        renderer=_render_lines,
    ),
    "intent_router": TraceStageRegistration(
        stage_id="intent_router",
        title="Intent router",
        order=2,
        schema_version=1,
        state_field_map=("intent_trace",),
        renderer=_render_lines,
    ),
    "meso_router": TraceStageRegistration(
        stage_id="meso_router",
        title="Meso router",
        order=3,
        schema_version=2,
        state_field_map=(
            "section_candidates",
            "meso_section_trace",
            "graph_traversal",
            "navigation_trace",
        ),
        renderer=_render_meso_router,
    ),
    "micro_extractor": TraceStageRegistration(
        stage_id="micro_extractor",
        title="Micro extractor",
        order=4,
        schema_version=2,
        state_field_map=(
            "evidence_chunks",
            "micro_ranked_count",
            "micro_rank_trace",
            "graph_traversal",
            "navigation_trace",
        ),
        renderer=_render_micro_extractor,
    ),
    "synthesize": TraceStageRegistration(
        stage_id="synthesize",
        title="Synthesize",
        order=5,
        schema_version=1,
        state_field_map=("answer", "status"),
        renderer=_render_lines,
    ),
}

REGISTERED_EVENT_TYPES = frozenset(
    {
        TraceEventType.STAGE_START,
        TraceEventType.STAGE_END,
        TraceEventType.LLM_IO,
        TraceEventType.ROUTING_DECISION,
        TraceEventType.EVIDENCE_SNAPSHOT,
    }
)
