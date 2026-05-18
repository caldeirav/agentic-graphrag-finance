"""CLI: ingest SEC filings."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from models.filing import FilingRef
from parsing.docling_pipeline import parse_filing_path
from parsing.edgar_fetch import download_filing, normalize_cik, parse_filing_metadata_from_path
from parsing.validators import validate_parsed_document


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC filings")
    parser.add_argument("--cik", required=True)
    parser.add_argument("--accession", default="")
    parser.add_argument("--form", default="10-K")
    parser.add_argument("--input", type=Path, help="Local HTML file (skip download)")
    parser.add_argument("--out", type=Path, default=Path("data/parsed"))
    parser.add_argument("--skip-docling", action="store_true")
    args = parser.parse_args()

    raw_dir = Path("data/raw/edgar") / normalize_cik(args.cik)
    if args.input:
        path = args.input
        filing = parse_filing_metadata_from_path(path, args.cik, args.form)
    else:
        filing = FilingRef(
            cik=normalize_cik(args.cik),
            accession=args.accession or "0000320193-24-000123",
            form_type=args.form,
            filed_at=__import__("datetime").date.today(),
            period_end=__import__("datetime").date.today(),
            source_uri="",
        )
        path = download_filing(filing, raw_dir)

    doc = parse_filing_path(path, filing, use_docling=not args.skip_docling)
    validate_parsed_document(doc)
    out_dir = args.out / normalize_cik(args.cik)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{doc.filing.accession}.json"
    out_file.write_text(doc.model_dump_json(indent=2))
    print(json.dumps({"parsed": str(out_file), "confidence": doc.parse_confidence}))


if __name__ == "__main__":
    main()
