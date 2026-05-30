"""Unit tests for benchmark materialize facade (011)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.benchmark_materialize import materialize_sampled_corpus
from models.benchmark_generation import SamplingManifest, SelectedIssuer
from models.corpus import CorpusMemberStatus
from models.enums import GraphNodeType
from models.graph import GraphManifest, GraphNode, GraphSnapshot


@patch("graph.store.load_snapshot")
@patch("cli.benchmark_materialize.run_materialize_pipeline")
def test_materialize_writes_corpus_bundle(mock_run, mock_load, tmp_path: Path):
    from datetime import UTC, datetime

    member = MagicMock()
    member.status = CorpusMemberStatus.INCLUDED
    member.resolution.accession = "0000320193-24-000123"
    job = MagicMock()
    job.snapshot_id = "snap-123"
    job.members = [member]
    mock_run.return_value = job
    mock_load.return_value = GraphSnapshot(
        snapshot_id="snap-123",
        issuer_id="AAPL",
        nodes=[
            GraphNode(
                node_id="n1",
                node_type=GraphNodeType.SECTION,
                label="Item7",
                properties={"section_slug": "Item7"},
            )
        ],
        edges=[],
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[],
            parser_version="test",
            graph_builder_version="test",
            storage_path=".",
        ),
    )
    sampling = SamplingManifest(
        manifest_id="m1",
        config_hash="sha256:abc",
        allowlist_hash="sha256:def",
        random_seed=0,
        selected_issuers=[
            SelectedIssuer(
                ticker="AAPL",
                accessions=["0000320193-24-000123"],
                selection_rationale=["fixture"],
            )
        ],
    )
    bundle, report = materialize_sampled_corpus(sampling, tmp_path, run_id="run1")
    assert bundle.issuer_snapshots[0].snapshot_id == "snap-123"
    assert (tmp_path / "corpus" / "graph_node_index.json").is_file()
    assert (tmp_path / "corpus_bundle.json").is_file()
    assert report.run_id == "run1"


@patch("graph.store.load_snapshot")
@patch("cli.benchmark_materialize.run_materialize_pipeline")
def test_materialize_skips_issuer_with_no_filings(mock_run, mock_load, tmp_path: Path):
    from datetime import UTC, datetime

    member = MagicMock()
    member.status = CorpusMemberStatus.INCLUDED
    member.resolution.accession = "0000320193-24-000123"
    job = MagicMock()
    job.snapshot_id = "snap-123"
    job.members = [member]
    mock_run.return_value = job
    mock_load.return_value = GraphSnapshot(
        snapshot_id="snap-123",
        issuer_id="AAPL",
        nodes=[],
        edges=[],
        manifest=GraphManifest(
            created_at=datetime.now(UTC),
            filing_refs=[],
            parser_version="test",
            graph_builder_version="test",
            storage_path=".",
        ),
    )
    sampling = SamplingManifest(
        manifest_id="m1",
        config_hash="sha256:abc",
        allowlist_hash="sha256:def",
        random_seed=0,
        selected_issuers=[
            SelectedIssuer(ticker="AAPL", accessions=["0000320193-24-000123"], selection_rationale=["fixture"]),
            SelectedIssuer(ticker="BAC", accessions=[], selection_rationale=["finder"]),
        ],
    )
    bundle, report = materialize_sampled_corpus(sampling, tmp_path, run_id="run1")
    mock_run.assert_called_once()
    assert len(bundle.issuer_snapshots) == 1
    assert report.rejections_by_reason["no_filings_sampled:BAC"] == 1
