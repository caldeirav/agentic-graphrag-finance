"""Atomic JSON checkpoint I/O for reproduction runs (013)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def write_json_atomic(path: Path, payload: Any, *, indent: int | None = 2) -> None:
    """Write JSON via temp file + rename for crash-safe checkpoints."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    text = json.dumps(payload, indent=indent, default=str)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)
