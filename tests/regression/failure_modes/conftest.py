"""Shared fixtures for failure-mode regression suite (019)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def load_failure_fixture():
    def _load(name: str) -> dict:
        path = Path(__file__).parent / name
        return json.loads(path.read_text(encoding="utf-8"))

    return _load
