"""CLI: run benchmark suite."""

from __future__ import annotations

import argparse
import json
import os

import tracing.bootstrap_env  # noqa: F401
from evaluation.registry import default_registry
from evaluation.runner import BenchmarkSuite, EvaluationRunner
from retrieval.service import QueryService


def main() -> None:
    parser = argparse.ArgumentParser(description="Run financial QA benchmarks")
    parser.add_argument("--suite", default="pilot")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--issuer-id", default="")
    parser.add_argument("--datasets", default="finder,finagentbench,financebench")
    parser.add_argument("--max-items", type=int, default=3)
    parser.add_argument("--mock-judge", action="store_true")
    args = parser.parse_args()

    if args.mock_judge:
        os.environ["USE_MOCK_JUDGE"] = "1"
    os.environ.setdefault("USE_MOCK_LLM", "1")

    suite = BenchmarkSuite(
        datasets=[d.strip() for d in args.datasets.split(",")],
        split=args.suite,
        max_items=args.max_items,
    )
    runner = EvaluationRunner(registry=default_registry())
    svc = QueryService(issuer_id=args.issuer_id or None)
    result = runner.run_suite(suite, args.snapshot_id, svc, issuer_id=args.issuer_id)
    print(json.dumps({"run_id": result.run_id, "items": len(result.items)}, indent=2))


if __name__ == "__main__":
    main()
