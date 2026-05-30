"""Verify exported tables against release checksums (012)."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path

from models.reproduction import ReleaseManifest, ToleranceBands

EXACT_METRICS = frozenset({"mrr", "map", "ndcg_at_10"})


@dataclass
class VerifyTablesResult:
    ok: bool
    diffs: list[str] = field(default_factory=list)

    @property
    def message(self) -> str:
        if self.ok:
            return "Table verification passed."
        return "Table verification failed:\n" + "\n".join(f"  - {d}" for d in self.diffs)


def _load_headline_metrics(tables_dir: Path) -> dict[tuple[str, str], float]:
    path = tables_dir / "headline.csv"
    out: dict[tuple[str, str], float] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if row.get("na_reason"):
                continue
            key = (row["variant_id"], row["metric_name"])
            out[key] = float(row["value"])
    return out


def verify_tables(
    manifest: ReleaseManifest,
    tables_dir: Path,
    expected: dict,
) -> VerifyTablesResult:
    diffs: list[str] = []
    actual = _load_headline_metrics(tables_dir)
    expected_headline = expected.get("headline", {})
    bands: ToleranceBands = manifest.tolerance_bands

    for key, expected_value in expected_headline.items():
        if "." not in key:
            continue
        variant_id, metric_name = key.split(".", 1)
        got = actual.get((variant_id, metric_name))
        if got is None:
            diffs.append(f"missing metric {key}")
            continue
        if metric_name in EXACT_METRICS or metric_name.startswith("structural_"):
            if abs(got - float(expected_value)) > 1e-9:
                diffs.append(f"exact mismatch {key}: expected {expected_value}, got {got}")
            continue
        tol = bands.mean_outcome_accuracy
        if metric_name == "rubric_alignment":
            tol = bands.mean_rubric_alignment
        elif metric_name == "trajectory_fidelity":
            tol = bands.mean_trajectory_fidelity
        if abs(got - float(expected_value)) > tol:
            diffs.append(
                f"tolerance mismatch {key}: expected {expected_value} ±{tol}, got {got}"
            )

    return VerifyTablesResult(ok=not diffs, diffs=diffs)
