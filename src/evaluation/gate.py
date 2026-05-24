"""Trajectory validation gate reporting (010)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from models.evaluation import ValidationStatus


@dataclass
class TrajectoryGateReport:
    total: int
    complete: int
    incomplete: int
    non_reproducible: int
    pass_rate: float
    gate_passed: bool
    judge_degraded: int = 0

    def format_summary(self) -> str:
        lines = [
            "trajectory_validation:",
            f"  total: {self.total}",
            f"  complete: {self.complete} ({self.pass_rate * 100:.1f}%)",
            f"  incomplete: {self.incomplete}",
            f"  non_reproducible: {self.non_reproducible}",
            f"  gate: {'PASS' if self.gate_passed else 'FAIL'}",
        ]
        if self.judge_degraded:
            lines.append(f"  judge_degraded: {self.judge_degraded}")
        return "\n".join(lines)


def load_gate_config(path: Path | None = None) -> dict:
    p = path or Path("configs/benchmarks/reference_trajectory_gate.yaml")
    return yaml.safe_load(p.read_text()) if p.exists() else {}


def compute_gate_report(
    validation_statuses: list[ValidationStatus],
    *,
    threshold: float = 0.9,
    judge_degraded: int = 0,
) -> TrajectoryGateReport:
    total = len(validation_statuses)
    complete = sum(1 for s in validation_statuses if s == ValidationStatus.COMPLETE)
    incomplete = sum(1 for s in validation_statuses if s == ValidationStatus.INCOMPLETE)
    non_rep = sum(1 for s in validation_statuses if s == ValidationStatus.NON_REPRODUCIBLE)
    rate = complete / total if total else 0.0
    return TrajectoryGateReport(
        total=total,
        complete=complete,
        incomplete=incomplete,
        non_reproducible=non_rep,
        pass_rate=rate,
        gate_passed=rate >= threshold,
        judge_degraded=judge_degraded,
    )


def load_reference_item_count(items_path: Path | None = None) -> int:
    cfg = load_gate_config()
    path = items_path or Path(cfg.get("items_path", "tests/fixtures/reference_trajectory_gate/items.jsonl"))
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text().splitlines() if line.strip())


def assert_gate_minimum_items(min_items: int = 50) -> None:
    count = load_reference_item_count()
    if count < min_items:
        raise ValueError(f"reference suite has {count} items; need {min_items}")
