#!/usr/bin/env python3
"""CLI wrapper for 022 outcome-score-ladder phase gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation.reproduction.investigation.phase_gate import (
    DEFAULT_COHORT_PATH,
    DEFAULT_VARIANT,
    evaluate_phase_gate,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check 022 phase cohort gate")
    parser.add_argument("--report", type=Path, required=True, help="Cohort repro output dir")
    parser.add_argument("--phase", required=True, choices=["A", "B", "C", "D", "E", "a", "b", "c", "d", "e"])
    parser.add_argument("--cohort", type=Path, default=DEFAULT_COHORT_PATH)
    parser.add_argument("--variant", default=DEFAULT_VARIANT)
    parser.add_argument("--json-out", type=Path, help="Write gate result JSON")
    args = parser.parse_args(argv)

    result = evaluate_phase_gate(
        report_dir=args.report,
        phase=args.phase.upper(),
        cohort_path=args.cohort,
        variant=args.variant,
    )

    print(json.dumps(result, indent=2))
    if args.json_out:
        args.json_out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    if result["passed"]:
        print(f"\nPASS phase {result['phase']}: {result['outcome_gt0']}/{result['outcome_total']} outcome>0")
        return 0

    print(
        f"\nFAIL phase {result['phase']}: {result['outcome_gt0']}/{result['outcome_total']} "
        f"outcome>0 (floor {result['target_floor']})",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
