"""CLI: run agentic query."""

from __future__ import annotations

import argparse
import json

import tracing.bootstrap_env  # noqa: F401
from contracts.query import QueryRequest
from retrieval.service import QueryService


def main() -> None:
    parser = argparse.ArgumentParser(description="Query SEC disclosure graph")
    parser.add_argument("--snapshot-id", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--issuer-id", default="")
    args = parser.parse_args()

    svc = QueryService(issuer_id=args.issuer_id or None)
    resp = svc.answer(
        QueryRequest(
            query=args.question,
            snapshot_id=args.snapshot_id,
            metadata={"issuer_id": args.issuer_id} if args.issuer_id else {},
        )
    )
    print(
        json.dumps(
            {
                "status": resp.status,
                "mlflow_run_id": resp.mlflow_run_id,
                "trajectory_uri": resp.trajectory_uri,
                "answer": resp.answer.model_dump(mode="json") if resp.answer else None,
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
