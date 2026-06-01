"""Per-item subgraph loading (013)."""

from __future__ import annotations

from pathlib import Path

import pytest

from evaluation.reproduction.accession_index import AccessionIndex
from evaluation.reproduction.errors import MissingAccessionsError, MissingBindingsError
from evaluation.reproduction.snapshot_loader import load_bundle_snapshot, load_item_subgraph


def test_item_subgraph_smaller_than_composite() -> None:
    bundle = Path("tests/fixtures/custom_judge")
    composite_id, composite = load_bundle_snapshot(bundle)
    index = AccessionIndex.build(bundle)
    accession = next(iter(index.accession_to_issuer))
    slice_id, slice_snap = load_item_subgraph(bundle, [accession], index, item_id="t1")
    assert slice_id.startswith("slice-")
    assert len(slice_snap.nodes) <= len(composite.nodes)


def test_empty_accessions_fail() -> None:
    bundle = Path("tests/fixtures/custom_judge")
    index = AccessionIndex.build(bundle)
    with pytest.raises(MissingBindingsError):
        load_item_subgraph(bundle, [], index, item_id="t2")
