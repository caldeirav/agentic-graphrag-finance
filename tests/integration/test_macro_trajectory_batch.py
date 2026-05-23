"""SC-003: batch audit of macro trajectory fields (T029a)."""

from __future__ import annotations

from unittest.mock import MagicMock

from evaluation.datasets.finagentbench import FinAgentBenchDataset
from retrieval.macro.models import ValidationStatus
from retrieval.orchestration.nodes.macro_router import macro_router

_REQUIRED = {
    "binding_source",
    "comparison_mode",
    "selected_accessions",
    "rationale",
    "validation_status",
}


def test_macro_trajectory_batch_audit(monkeypatch, aapl_macro_snapshot):
    monkeypatch.setenv("USE_MOCK_LLM", "1")
    items = FinAgentBenchDataset().load_macro_binding_slice()[:50]
    assert len(items) >= 50
    api = MagicMock()
    api.get_snapshot.return_value = aapl_macro_snapshot
    for item in items:
        if item.expect_binding_failure:
            continue
        out = macro_router(
            {
                "query": item.question,
                "snapshot_id": aapl_macro_snapshot.snapshot_id,
                "filing_set": [],
                "cli_prebound": False,
            },
            graph_api=api,
        )
        record = out.get("macro_binding_record")
        assert record is not None
        payload = record.to_trajectory_dict()
        assert _REQUIRED.issubset(payload.keys())
        assert payload["validation_status"] in (
            ValidationStatus.APPROVED.value,
            ValidationStatus.NARROWED.value,
        )
        assert payload["rationale"]
