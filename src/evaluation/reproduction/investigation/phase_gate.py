"""022 outcome-score-ladder phase gate evaluation."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from evaluation.generation.review.queue import _load_repro_results, _outcome_score
from evaluation.reproduction.smoke_gate import _abstention_like, _value_alignment

_REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TARGETS_PATH = _REPO_ROOT / "specs/022-outcome-score-ladder/fixtures/cohort_phase_targets.json"
DEFAULT_COHORT_PATH = (
    _REPO_ROOT / "specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json"
)
DEFAULT_VARIANT = "graph-full"

_PHASE_KEYS = {
    "A": "phase_a_ratio",
    "B": "phase_b_point",
    "C": "phase_c_slice",
    "D": "phase_d_html",
    "E": "phase_e_segment",
}


def load_cohort_item_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(x) for x in payload]
    ids = payload.get("item_ids")
    if not isinstance(ids, list):
        msg = f"Expected item_ids[] in {path}"
        raise ValueError(msg)
    return [str(x) for x in ids]


def _temporal_mismatch(result) -> bool:
    snap = result.trajectory_snapshot if result else None
    if not isinstance(snap, dict):
        return False
    return "temporal_mismatch" in json.dumps(snap).lower()


def _forbidden_hits(answer: str, patterns: list[str]) -> int:
    return sum(1 for pat in patterns if re.search(pat, answer, re.I))


def _phase_config(targets: dict, phase: str) -> dict:
    return targets[_PHASE_KEYS[phase.upper()]]


def _floor_for_phase(cfg: dict, phase: str) -> int:
    if phase.upper() == "A":
        return int(cfg.get("gate_outcome_gt0_floor", 2))
    return int(cfg.get("gate_outcome_gt0_floor_cumulative", 0))


def _stretch_for_phase(cfg: dict, phase: str) -> int | None:
    if phase.upper() == "A":
        stretch = cfg.get("gate_outcome_gt0_stretch")
    else:
        stretch = cfg.get("gate_outcome_gt0_stretch_cumulative")
    if stretch is None and phase.upper() == "E":
        stretch = cfg.get("gate_outcome_gt0_sc001_target")
    return int(stretch) if stretch is not None else None


def evaluate_phase_gate(
    *,
    report_dir: Path,
    phase: str,
    cohort_path: Path | None = None,
    variant: str = DEFAULT_VARIANT,
    targets_path: Path = DEFAULT_TARGETS_PATH,
) -> dict:
    phase = phase.upper()
    if phase not in _PHASE_KEYS:
        msg = f"Unknown phase {phase!r}; expected A–E"
        raise ValueError(msg)

    targets = json.loads(targets_path.read_text(encoding="utf-8"))
    cfg = _phase_config(targets, phase)
    item_ids = load_cohort_item_ids(cohort_path or DEFAULT_COHORT_PATH)
    results = _load_repro_results(report_dir, variant)

    outcomes: list[float] = []
    vas: list[float] = []
    outcome_gt0 = 0
    abstain_like = 0
    temporal_mismatch = 0
    forbidden_total = 0
    primary_outcomes: dict[str, dict[str, float]] = {}

    forbidden_patterns = cfg.get("forbidden_answer_patterns") or []

    for item_id in item_ids:
        row = results.get(item_id)
        outcome = _outcome_score(row) if row else 0.0
        outcomes.append(outcome)
        if outcome > 0:
            outcome_gt0 += 1
        vas.append(float(_value_alignment(row) if row else 0.0))
        if row and _abstention_like(row):
            abstain_like += 1
        if row and _temporal_mismatch(row):
            temporal_mismatch += 1
        answer = (row.answer.text if row and row.answer else "") or ""
        forbidden_total += _forbidden_hits(answer, forbidden_patterns)

    for pid in cfg.get("primary_item_ids") or []:
        row = results.get(pid)
        primary_outcomes[pid] = {
            "outcome_score": _outcome_score(row) if row else 0.0,
            "value_alignment": float(_value_alignment(row) if row else 0.0),
        }

    floor = _floor_for_phase(cfg, phase)
    stretch = _stretch_for_phase(cfg, phase)
    passed = outcome_gt0 >= floor

    if phase == "A" and forbidden_total > 0:
        passed = False
    if phase == "C":
        max_tm = int(cfg.get("gate_macro_temporal_mismatch_max", 1))
        if temporal_mismatch > max_tm:
            passed = False
    if phase == "D":
        abstain_max = cfg.get("gate_abstain_max")
        if abstain_max is not None and abstain_like > int(abstain_max):
            passed = False

    n = len(item_ids)
    return {
        "phase": phase,
        "report_dir": str(report_dir),
        "variant": variant,
        "outcome_gt0": outcome_gt0,
        "outcome_total": n,
        "mean_outcome_score": sum(outcomes) / n if n else 0.0,
        "mean_value_alignment": sum(vas) / n if n else 0.0,
        "abstain_like_count": abstain_like,
        "temporal_mismatch_count": temporal_mismatch,
        "forbidden_pattern_hits": forbidden_total,
        "target_floor": floor,
        "target_stretch": stretch,
        "passed": passed,
        "primary_item_outcomes": primary_outcomes,
        "checked_at": datetime.now(tz=UTC).isoformat(),
    }
