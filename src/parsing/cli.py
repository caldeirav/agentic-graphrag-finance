"""CLI: parse ingested XBRL packages."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ingestion import fetch_filing
from parsing.sec_download_adapter import parse_from_cache, write_parsed_document
from parsing.validators import validate_parsed_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse ingested SEC XBRL packages")
    parser.add_argument("--ticker", default="AAPL")
    parser.add_argument("--cik", default="")
    parser.add_argument("--accession", default="")
    parser.add_argument("--form", default="10-K")
    parser.add_argument("--out", type=Path, default=Path("data/parsed"))
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    entry = fetch_filing(
        ticker=args.ticker or None,
        cik=args.cik or None,
        accession=args.accession or None,
        form_type=args.form,
        force_refresh=args.force_refresh,
    )
    doc = parse_from_cache(entry)
    validate_parsed_document(doc)
    ticker = args.ticker.upper() if args.ticker else doc.filing.cik
    out_path = write_parsed_document(doc, args.out, ticker=ticker)
    print(json.dumps({"parsed": str(out_path), "confidence": doc.parse_confidence}))


if __name__ == "__main__":
    main()
