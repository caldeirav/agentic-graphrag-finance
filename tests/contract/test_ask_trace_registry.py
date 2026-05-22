"""Registry must match ask-graph stages (FR-006)."""

from __future__ import annotations

import typing

from retrieval.orchestration.graph import get_ask_graph_stage_ids
from retrieval.orchestration.state import AgentState
from tracing.console_trace.registry import ASK_TRACE_REGISTRY, REGISTERED_EVENT_TYPES


def test_graph_stages_match_registry() -> None:
    graph_ids = get_ask_graph_stage_ids()
    registry_ids = set(ASK_TRACE_REGISTRY.keys())
    assert graph_ids == registry_ids, (
        f"mismatch graph={sorted(graph_ids)} registry={sorted(registry_ids)}"
    )


def test_registry_state_fields_exist_on_agent_state() -> None:
    hints = typing.get_type_hints(AgentState, include_extras=True)
    for reg in ASK_TRACE_REGISTRY.values():
        for field in reg.state_field_map:
            assert field in hints, f"{reg.stage_id} maps unknown AgentState field {field}"


def test_event_types_registered() -> None:
    from tracing.console_trace.models import TraceEventType

    for et in TraceEventType:
        assert et in REGISTERED_EVENT_TYPES
