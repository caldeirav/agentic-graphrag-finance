"""Outcome smoke gate for paper-v2.0 agent iteration (graph-full subset)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from models.evaluation import BenchmarkResult

DEFAULT_SMOKE_ITEM_IDS_REL = "smoke_dev_item_ids.json"
DEFAULT_FINAGENT_SMOKE_ITEM_IDS_REL = "smoke_finagentbench_item_ids.json"
DEFAULT_VARIANT = "graph-full"

# Gate thresholds — tuned after smoke v6 (2026-06); raise when agent improves further.
DEFAULT_THRESHOLDS: dict[str, float | int] = {
    "min_task_success": 0.45,
    "max_mrr_zero_share": 0.10,
    "max_mrr_ok_va_zero": 12,
    "max_abstention_like_share": 0.10,
    "min_items_with_va": 25,
}


@dataclass
class SmokeGateThresholds:
    min_task_success: float = 0.45
    max_mrr_zero_share: float = 0.10
    max_mrr_ok_va_zero: int = 12
    max_abstention_like_share: float = 0.10
    min_items_with_va: int = 25

    @classmethod
    def from_mapping(cls, raw: dict[str, float | int] | None) -> SmokeGateThresholds:
        if not raw:
            return cls()
        return cls(
            min_task_success=float(raw.get("min_task_success", cls.min_task_success)),
            max_mrr_zero_share=float(raw.get("max_mrr_zero_share", cls.max_mrr_zero_share)),
            max_mrr_ok_va_zero=int(raw.get("max_mrr_ok_va_zero", cls.max_mrr_ok_va_zero)),
            max_abstention_like_share=float(
                raw.get("max_abstention_like_share", cls.max_abstention_like_share)
            ),
            min_items_with_va=int(raw.get("min_items_with_va", cls.min_items_with_va)),
        )


@dataclass
class SmokeGateMetrics:
    n: int = 0
    task_success: float = 0.0
    mrr_zero: int = 0
    mrr_ok_va_zero: int = 0
    va_positive: int = 0
    va_one: int = 0
    abstention_like: int = 0
    by_profile: dict[str, float] = field(default_factory=dict)


@dataclass
class SmokeGateResult:
    ok: bool
    metrics: SmokeGateMetrics
    failures: list[str] = field(default_factory=list)
    thresholds: SmokeGateThresholds = field(default_factory=SmokeGateThresholds)


_ABSTENTION_RE = re.compile(
    r"\b(cannot|can't|unable to|insufficient evidence|no information|not provided|"
    r"does not contain|do not contain|cannot identify|cannot determine|cannot complete|"
    r"cannot fulfill|not available in the)\b",
    re.I,
)


def smoke_item_ids_path(bundle_root: Path, rel: str | None = None) -> Path:
    return bundle_root / (rel or DEFAULT_SMOKE_ITEM_IDS_REL)


def load_smoke_item_ids(bundle_root: Path, rel: str | None = None) -> list[str]:
    path = smoke_item_ids_path(bundle_root, rel)
    if not path.is_file():
        msg = f"Smoke item list not found: {path}"
        raise FileNotFoundError(msg)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return list(payload)
    ids = payload.get("item_ids")
    if not isinstance(ids, list) or not ids:
        msg = f"Smoke item list at {path} must contain item_ids[]"
        raise ValueError(msg)
    return [str(i) for i in ids]


def build_stratified_smoke_ids(
    bundle_root: Path,
    *,
    split: str = "dev",
    count: int = 50,
) -> list[str]:
    """Build a stratified smoke list from the bundle dev split (profile × answer_type)."""
    items_path = bundle_root / "items" / f"{split}.jsonl"
    if not items_path.is_file():
        msg = f"Split not found: {items_path}"
        raise FileNotFoundError(msg)
    items = [
        json.loads(line)
        for line in items_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    buckets: dict[tuple[str, str], list[str]] = {}
    for row in items:
        prof = str(row.get("inspiration_profile") or "?")
        gt = row.get("ground_truth") or {}
        at = str(gt.get("answer_type") or "?")
        buckets.setdefault((prof, at), []).append(row["item_id"])

    def _priority(key: tuple[str, str]) -> tuple[int, str]:
        _prof, at = key
        order = {
            "comparison_structured": 0,
            "numeric": 1,
            "narrative": 2,
            "short_label": 3,
        }
        return (order.get(at, 9), _prof)

    per_bucket = max(2, count // max(len(buckets), 1))
    selected: list[str] = []
    for key in sorted(buckets.keys(), key=_priority):
        selected.extend(sorted(buckets[key])[:per_bucket])

    seen: set[str] = set()
    out: list[str] = []
    for iid in selected:
        if iid in seen:
            continue
        seen.add(iid)
        out.append(iid)
        if len(out) >= count:
            break

    if len(out) < count:
        for row in sorted(items, key=lambda r: r["item_id"]):
            iid = row["item_id"]
            if iid in seen:
                continue
            seen.add(iid)
            out.append(iid)
            if len(out) >= count:
                break
    return out


def build_finagent_smoke_ids(
    bundle_root: Path,
    *,
    split: str = "dev",
) -> list[str]:
    """All finagentbench item ids in the bundle split (fast iteration subset)."""
    items_path = bundle_root / "items" / f"{split}.jsonl"
    if not items_path.is_file():
        msg = f"Split not found: {items_path}"
        raise FileNotFoundError(msg)
    ids: list[str] = []
    for line in items_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("inspiration_profile") == "finagentbench":
            ids.append(str(row["item_id"]))
    return sorted(ids)


def write_smoke_item_ids_file(
    bundle_root: Path,
    item_ids: list[str],
    rel: str,
    *,
    label: str = "",
) -> Path:
    path = bundle_root / rel
    payload = {
        "version": 1,
        "count": len(item_ids),
        "label": label or rel,
        "item_ids": item_ids,
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def resolve_smoke_item_ids_path(subset: str | None) -> str:
    if subset == "finagent":
        return DEFAULT_FINAGENT_SMOKE_ITEM_IDS_REL
    return DEFAULT_SMOKE_ITEM_IDS_REL


def _value_alignment(row: BenchmarkResult) -> float:
    if row.judge_verdict and row.judge_verdict.scores:
        va = row.judge_verdict.scores.get("value_alignment")
        if va is not None:
            return float(va)
    return float(row.outcome_score or 0.0)


def _mrr(row: BenchmarkResult) -> float:
    if row.ranking_metrics is None:
        return 0.0
    return float(row.ranking_metrics.mrr or 0.0)


def _abstention_like(row: BenchmarkResult) -> bool:
    text = (row.answer.text if row.answer else "") or ""
    return bool(_ABSTENTION_RE.search(text))


def compute_smoke_metrics(
    rows: list[BenchmarkResult],
    *,
    profile_by_item: dict[str, str] | None = None,
) -> SmokeGateMetrics:
    if not rows:
        return SmokeGateMetrics()
    va_scores = [_value_alignment(r) for r in rows]
    mrr_scores = [_mrr(r) for r in rows]
    n = len(rows)
    mrr_ok_va_zero = sum(1 for va, m in zip(va_scores, mrr_scores, strict=True) if m >= 0.5 and va == 0.0)
    by_prof: dict[str, list[float]] = {}
    if profile_by_item:
        for row, va in zip(rows, va_scores, strict=True):
            prof = profile_by_item.get(row.item_id, "?")
            by_prof.setdefault(prof, []).append(va)
    return SmokeGateMetrics(
        n=n,
        task_success=sum(va_scores) / n,
        mrr_zero=sum(1 for m in mrr_scores if m == 0.0),
        mrr_ok_va_zero=mrr_ok_va_zero,
        va_positive=sum(1 for v in va_scores if v > 0.0),
        va_one=sum(1 for v in va_scores if v >= 1.0),
        abstention_like=sum(1 for r in rows if _abstention_like(r)),
        by_profile={p: sum(v) / len(v) for p, v in by_prof.items()},
    )


def evaluate_smoke_gate(
    results_path: Path,
    item_ids: list[str],
    *,
    thresholds: SmokeGateThresholds | None = None,
    profile_by_item: dict[str, str] | None = None,
) -> SmokeGateResult:
    thresholds = thresholds or SmokeGateThresholds()
    if not results_path.is_file():
        return SmokeGateResult(
            ok=False,
            metrics=SmokeGateMetrics(),
            failures=[f"Missing results: {results_path}"],
            thresholds=thresholds,
        )
    raw = json.loads(results_path.read_text(encoding="utf-8"))
    by_id = {row["item_id"]: BenchmarkResult.model_validate(row) for row in raw}
    missing = [iid for iid in item_ids if iid not in by_id]
    rows = [by_id[iid] for iid in item_ids if iid in by_id]
    metrics = compute_smoke_metrics(rows, profile_by_item=profile_by_item)
    failures: list[str] = []

    if missing:
        failures.append(f"missing {len(missing)}/{len(item_ids)} smoke items in results")
    if metrics.n == 0:
        failures.append("no smoke items scored")
        return SmokeGateResult(ok=False, metrics=metrics, failures=failures, thresholds=thresholds)

    if metrics.task_success < thresholds.min_task_success:
        failures.append(
            f"task_success {metrics.task_success:.3f} < {thresholds.min_task_success:.3f}"
        )
    mrr_zero_share = metrics.mrr_zero / metrics.n
    if mrr_zero_share > thresholds.max_mrr_zero_share:
        failures.append(
            f"MRR=0 on {metrics.mrr_zero}/{metrics.n} ({mrr_zero_share:.0%}) "
            f"> max {thresholds.max_mrr_zero_share:.0%}"
        )
    if metrics.mrr_ok_va_zero > thresholds.max_mrr_ok_va_zero:
        failures.append(
            f"MRR≥0.5 & VA=0 on {metrics.mrr_ok_va_zero} items "
            f"> max {thresholds.max_mrr_ok_va_zero}"
        )
    abst_share = metrics.abstention_like / metrics.n
    if abst_share > thresholds.max_abstention_like_share:
        failures.append(
            f"abstention-like answers {metrics.abstention_like}/{metrics.n} ({abst_share:.0%}) "
            f"> max {thresholds.max_abstention_like_share:.0%}"
        )
    if metrics.va_positive < thresholds.min_items_with_va:
        failures.append(
            f"VA>0 on {metrics.va_positive} items < min {thresholds.min_items_with_va}"
        )

    return SmokeGateResult(
        ok=not failures,
        metrics=metrics,
        failures=failures,
        thresholds=thresholds,
    )


def format_smoke_report(result: SmokeGateResult, *, item_ids: list[str] | None = None) -> str:
    m = result.metrics
    lines = [
        "Smoke gate report",
        f"  items: {m.n}" + (f" / {len(item_ids)}" if item_ids else ""),
        f"  task_success: {m.task_success:.4f}",
        f"  MRR=0: {m.mrr_zero}/{m.n} ({(m.mrr_zero / m.n if m.n else 0):.0%})",
        f"  MRR≥0.5 & VA=0: {m.mrr_ok_va_zero}",
        f"  VA>0: {m.va_positive}/{m.n}  VA=1: {m.va_one}/{m.n}",
        f"  abstention-like: {m.abstention_like}/{m.n}",
    ]
    if m.by_profile:
        lines.append("  by profile:")
        for prof, val in sorted(m.by_profile.items()):
            lines.append(f"    {prof}: {val:.3f}")
    if result.failures:
        lines.append("  FAIL:")
        for f in result.failures:
            lines.append(f"    - {f}")
    else:
        lines.append("  PASS")
    return "\n".join(lines)


def profile_map_from_bundle(bundle_root: Path, split: str = "dev") -> dict[str, str]:
    path = bundle_root / "items" / f"{split}.jsonl"
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["item_id"]] = str(row.get("inspiration_profile") or "?")
    return out
