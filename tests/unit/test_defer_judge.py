"""Defer-judge configuration and guards (013)."""

from __future__ import annotations

from evaluation.reproduction.defer_config import (
    is_final_judge_status,
    resolve_defer_config,
    should_skip_post_query_audit,
)


def test_should_skip_post_query_audit_requires_benchmark_item(monkeypatch) -> None:
    monkeypatch.setenv("REPRO_DEFER_JUDGE", "1")
    assert not should_skip_post_query_audit({})
    assert should_skip_post_query_audit({"benchmark_item": "i1"})


def test_resolve_defer_config_cli_override(monkeypatch) -> None:
    monkeypatch.delenv("REPRO_DEFER_JUDGE", raising=False)
    cfg = resolve_defer_config(cli_defer=True)
    assert cfg.enabled is True
    assert cfg.concurrency >= 1


def test_is_final_judge_status() -> None:
    assert is_final_judge_status("ok")
    assert is_final_judge_status("degraded")
    assert not is_final_judge_status("pending")
