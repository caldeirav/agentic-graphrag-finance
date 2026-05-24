#!/usr/bin/env python3
"""Build reference_trajectory_gate items.jsonl (≥50 rows)."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLD = ROOT / "tests/fixtures/gold_path/gold_path.jsonl"
OUT = ROOT / "tests/fixtures/reference_trajectory_gate/items.jsonl"
MIN_ITEMS = 50


def main() -> None:
    rows: list[dict] = []
    if GOLD.exists():
        for line in GOLD.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            gp = json.loads(line)
            rows.append(
                {
                    "item_id": gp.get("id", f"gp-{len(rows)}"),
                    "source": "gold_path",
                    "question": gp.get("query", ""),
                    "gold_path_row": gp,
                }
            )
    macro_stubs = [
        "latest_annual",
        "latest_quarter",
        "prior_quarter",
        "yoy_revenue",
        "qoq_compare",
        "latest_annual",
    ]
    for i, stub in enumerate(macro_stubs):
        rows.append(
            {
                "item_id": f"macro-{stub}-{i}",
                "source": "macro_binding",
                "question": f"Macro binding scenario {stub}",
                "macro_stub": stub,
            }
        )
    tv_dir = ROOT / "tests/fixtures/trajectory_validation"
    for j, path in enumerate(sorted(tv_dir.glob("*.json"))):
        if path.name == "manifest.json":
            continue
        rows.append(
            {
                "item_id": f"tv-{path.stem}",
                "source": "trajectory_validation",
                "question": f"Validator fixture {path.stem}",
                "trajectory_fixture": path.name,
            }
        )
    if len(rows) < MIN_ITEMS:
        raise SystemExit(f"reference suite has {len(rows)} items; need {MIN_ITEMS}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")
    print(f"Wrote {len(rows)} items to {OUT}")


if __name__ == "__main__":
    main()
