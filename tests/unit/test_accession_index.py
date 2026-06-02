"""Accession index for per-item subgraphs (013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.reproduction.accession_index import AccessionIndex
from evaluation.reproduction.errors import MissingAccessionsError


def test_accession_index_builds_from_fixture() -> None:
    bundle = Path("tests/fixtures/custom_judge")
    index = AccessionIndex.build(bundle)
    assert index.accession_to_issuer


def test_missing_accession_raises() -> None:
    bundle = Path("tests/fixtures/custom_judge")
    index = AccessionIndex.build(bundle)
    with pytest.raises(MissingAccessionsError):
        index.resolve_accessions("item-x", ["0000000000-00-000000"])
