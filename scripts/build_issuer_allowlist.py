#!/usr/bin/env python3
"""Build committed issuer allowlist for custom-judge generation (011)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "configs/benchmarks/issuer_allowlist_v1.json"
FIXTURE_DOWNLOADS = REPO_ROOT / "tests/fixtures/sec_downloads"

# Subset of tickers commonly present in FinanceBench open releases (provenance tag only).
FINANCEBENCH_TICKERS: tuple[str, ...] = (
    "AAPL",
    "AMZN",
    "GOOGL",
    "JPM",
    "MSFT",
    "NVDA",
    "WMT",
)

# FinAgentBench / project fixture overlap.
FIXTURE_TICKERS: tuple[str, ...] = ("AAPL",)

# FinDER-style coverage (ticker symbols extracted from public sample queries).
FINDER_TICKERS: tuple[str, ...] = ("AAPL", "BAC", "KO", "XOM")

# Sector-diverse expansion for v1 benchmark corpus (~20 issuers total after merge).
BENCHMARK_UNIVERSE_TICKERS: tuple[str, ...] = (
    "CAT",  # industrials
    "CVX",  # energy
    "DIS",  # media / entertainment
    "HD",  # consumer discretionary / retail
    "JNJ",  # healthcare
    "META",  # communication / tech
    "PG",  # consumer staples
    "TSLA",  # automotive / tech
    "UNH",  # healthcare / managed care
    "V",  # financials / payments
)


def _canonical_payload(entries: list[dict[str, object]], provenance: str) -> dict[str, object]:
    sorted_entries = sorted(entries, key=lambda e: str(e["ticker"]))
    return {
        "allowlist_id": "issuer_allowlist_v1",
        "provenance": provenance,
        "entries": sorted_entries,
    }


def _content_hash(payload: dict[str, object]) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _merge_entries() -> list[dict[str, object]]:
    by_ticker: dict[str, set[str]] = {}

    def add(ticker: str, source: str) -> None:
        key = ticker.upper().strip()
        if not key:
            return
        by_ticker.setdefault(key, set()).add(source)

    for ticker in FINANCEBENCH_TICKERS:
        add(ticker, "financebench")
    for ticker in FINDER_TICKERS:
        add(ticker, "finder")
    for ticker in BENCHMARK_UNIVERSE_TICKERS:
        add(ticker, "benchmark_universe")
    for ticker in FIXTURE_TICKERS:
        add(ticker, "finagentbench")
    if FIXTURE_DOWNLOADS.is_dir():
        for child in sorted(FIXTURE_DOWNLOADS.iterdir()):
            if child.is_dir():
                add(child.name, "fixture")

    return [
        {"ticker": ticker, "sources": sorted(sources)}
        for ticker, sources in sorted(by_ticker.items())
    ]


def build_allowlist(output: Path) -> dict[str, object]:
    provenance = (
        "Union of FinanceBench-style tickers, FinDER sample tickers, "
        "sector-diverse benchmark_universe tickers, FinAgentBench/project fixtures, "
        "and tests/fixtures/sec_downloads"
    )
    entries = _merge_entries()
    payload = _canonical_payload(entries, provenance)
    payload["content_hash"] = _content_hash(
        {"allowlist_id": payload["allowlist_id"], "entries": payload["entries"]}
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Build issuer allowlist JSON for custom-judge")
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Output path (default: configs/benchmarks/issuer_allowlist_v1.json)",
    )
    args = parser.parse_args()
    payload = build_allowlist(args.output)
    print(f"Wrote {len(payload['entries'])} issuers to {args.output}")


if __name__ == "__main__":
    main()
