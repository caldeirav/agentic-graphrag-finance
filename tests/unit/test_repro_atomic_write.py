"""Unit tests for atomic JSON checkpoints (013)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.io import write_json_atomic


def test_write_json_atomic_replaces_file(tmp_path: Path) -> None:
    target = tmp_path / "results.json"
    write_json_atomic(target, [{"item_id": "a"}])
    write_json_atomic(target, [{"item_id": "b"}])
    rows = json.loads(target.read_text(encoding="utf-8"))
    assert rows == [{"item_id": "b"}]
    assert not (tmp_path / "results.json.tmp").exists()
