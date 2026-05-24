"""Generate gold_path.jsonl labels from navigation eval snapshot (009)."""

from __future__ import annotations

import json
from pathlib import Path

DOC = "doc-0000320193-24-000123"
ACC = "0000320193-24-000123"


def generate_gold_path_items() -> list[dict]:
    items: list[dict] = []

    def add(
        item_id: str,
        query: str,
        required: list[str],
        edges: list[list[str]] | None = None,
    ) -> None:
        items.append(
            {
                "id": item_id,
                "query": query,
                "expected_accessions": [ACC],
                "required_chunk_node_ids": required,
                "acceptable_edge_sequences": edges or [["CONTAINS"]],
                "multi_filing_required": False,
            }
        )

    add("gp-001", "What risk factors are discussed in management discussion and analysis?", [])
    add("gp-002", "Summarize accounting policies in the notes to financial statements", [])
    add("gp-003", "What was total net sales in the revenue table?", [f"{DOC}-table-revenue-row-0"])
    add(
        "gp-004",
        "What does the footnote say about revenue recognition?",
        [f"{DOC}-fn-rev"],
        [["CONTAINS", "FOOTNOTE_OF"], ["FOOTNOTE_OF"]],
    )
    add("gp-005", "What are total assets on the balance sheet table?", [f"{DOC}-table-assets-row-0"])
    add("gp-006", "How much revenue came from products?", [f"{DOC}-table-revenue-row-1"])

    templates = [
        ("risk competition supply chain", "gp-mda"),
        ("accounting policies estimates", "gp-notes"),
        ("assets liabilities fiscal year", "gp-bs"),
        ("net sales revenue 2024", "gp-rev"),
        ("products segment sales", "gp-prod"),
        ("revenue recognition control customer", "gp-fn"),
        ("total assets reported", "gp-ast"),
    ]
    for words, prefix in templates:
        for i in range(5):
            add(f"{prefix}-{i+1:02d}", f"What does the filing say about {words}?", [])

    chunk_rows = [
        (f"{DOC}-table-revenue-row-0", "total net sales revenue 391035"),
        (f"{DOC}-table-revenue-row-1", "products revenue segment"),
        (f"{DOC}-table-assets-row-0", "total assets balance sheet"),
        (f"{DOC}-fn-rev", "footnote revenue recognition policy"),
        (f"{DOC}-sec-mda-body", "MD&A risk factors discussion"),
        (f"{DOC}-sec-notes-body", "notes accounting policies"),
        (f"{DOC}-sec-bs-body", "balance sheet assets liabilities"),
    ]
    for chunk_id, words in chunk_rows:
        for i in range(2):
            add(
                f"gp-chunk-{chunk_id.split('-')[-1]}-{i+1}",
                f"Provide details about {words}",
                [chunk_id],
            )

    while len(items) < 42:
        n = len(items) + 1
        add(f"gp-pad-{n:03d}", "Summarize disclosure information from the filing", [])

    return items[:42]


def write_gold_path_jsonl(path: Path | None = None) -> Path:
    out = path or Path("tests/fixtures/gold_path/gold_path.jsonl")
    out.parent.mkdir(parents=True, exist_ok=True)
    items = generate_gold_path_items()
    with out.open("w") as f:
        for row in items:
            f.write(json.dumps(row) + "\n")
    return out


if __name__ == "__main__":
    p = write_gold_path_jsonl()
    print(f"wrote {len(generate_gold_path_items())} items to {p}")
