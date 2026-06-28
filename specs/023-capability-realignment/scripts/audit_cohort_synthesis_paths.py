#!/usr/bin/env python3
"""Audit synthesis paths on numeric cohort (023 SC-003 / SC-004)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[3]
_DEFAULT_COHORT = (
    _REPO / "specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json"
)
_THRESHOLDS = Path(__file__).resolve().parents[1] / "fixtures/cohort_gate_thresholds.json"

_LLM_NARRATIVE = re.compile(
    r"\b(cannot be calculated|approximately \d|dividing the|provided evidence lacks)\b",
    re.I,
)
_STRUCTURED_ABSTAIN = re.compile(r"^Insufficient evidence:", re.I)
_COMPUTED = re.compile(r"Computed as .+:", re.I)


def _load_item_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [str(x) for x in payload]
    return [str(x) for x in payload["item_ids"]]


def classify_answer(text: str, synthesis_path: str) -> str:
    if synthesis_path in ("computed_numeric", "numeric_abstain"):
        return synthesis_path
    if _COMPUTED.search(text or ""):
        return "computed_numeric"
    if _STRUCTURED_ABSTAIN.match((text or "").strip()):
        return "numeric_abstain"
    if _LLM_NARRATIVE.search(text or ""):
        return "live_llm"
    if text and len(text) > 50:
        return "structured_llm"
    return "other"


def audit(report_dir: Path, cohort_path: Path) -> dict:
    results_path = report_dir / "graph-full" / "results.json"
    rows = json.loads(results_path.read_text(encoding="utf-8"))
    by_id = {r["item_id"]: r for r in rows}
    item_ids = _load_item_ids(cohort_path)

    paths_missing = 0
    forbidden = 0
    allowed = 0
    by_class: dict[str, int] = {}
    details: list[dict] = []

    for iid in item_ids:
        row = by_id.get(iid, {})
        snap = row.get("trajectory_snapshot") or {}
        syn = str(snap.get("synthesis_path") or "")
        text = (row.get("answer") or {}).get("text") or ""
        if not syn:
            paths_missing += 1
        cls = classify_answer(text, syn)
        by_class[cls] = by_class.get(cls, 0) + 1
        if cls in ("live_llm", "structured_llm"):
            forbidden += 1
        elif cls in ("computed_numeric", "numeric_abstain"):
            allowed += 1
        details.append({"item_id": iid, "synthesis_path": syn, "path_class": cls, "outcome": row.get("outcome_score", 0)})

    thresholds = json.loads(_THRESHOLDS.read_text(encoding="utf-8"))["m1_telemetry"]
    passed = (
        paths_missing <= (26 - int(thresholds["min_synthesis_path_populated"]))
        and forbidden <= int(thresholds["max_numeric_live_llm"])
        + int(thresholds["max_numeric_structured_llm"])
    )
    return {
        "report_dir": str(report_dir),
        "paths_missing": paths_missing,
        "forbidden_llm_paths": forbidden,
        "allowed_numeric_paths": allowed,
        "by_class": by_class,
        "passed": passed,
        "details": details,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit 023 numeric synthesis paths")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--cohort", type=Path, default=_DEFAULT_COHORT)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)

    result = audit(args.report, args.cohort)
    print(json.dumps({k: v for k, v in result.items() if k != "details"}, indent=2))
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if not result["passed"]:
        print("\nFAIL: numeric cohort still uses LLM fallback or missing synthesis_path", file=sys.stderr)
        return 1
    print("\nPASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
