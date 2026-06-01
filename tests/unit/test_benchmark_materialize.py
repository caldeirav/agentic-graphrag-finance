"""Unit tests for benchmark materialize facade (011)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from cli.benchmark_materialize import materialize_sampled_corpus
from models.benchmark_generation import SamplingManifest, SelectedIssuer
from models.corpus import CorpusMemberStatus
from models.enums import GraphNodeType
from models.graph import GraphManifest, GraphNode, GraphSnapshot


def _seed_graph_files(graphs_root: Path, ticker: str, snapshot_id: str) -> None:
    issuer_dir = graphs_root / ticker
    issuer_dir.mkdir(parents=True, exist_ok=True)
    (issuer_dir / f"{snapshot_id}.graphml").write_text("<graphml/>", encoding="utf-8")
    (issuer_dir / f"{snapshot_id}.manifest.json").write_text("{}", encoding="utf-8")


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
    graphs_root = tmp_path / "graphs"
    _seed_graph_files(graphs_root, "AAPL", "snap-123")
    bundle, report = materialize_sampled_corpus(
        sampling, tmp_path, graphs_root=graphs_root, run_id="run1"
    )
    assert bundle.issuer_snapshots[0].snapshot_id == "snap-123"
    assert (tmp_path / "corpus" / "graph_node_index.json").is_file()
    assert (tmp_path / "corpus_bundle.json").is_file()
    assert report.run_id == "run1"


@patch("graph.store.load_snapshot")
@patch("cli.benchmark_materialize.run_materialize_pipeline")
def test_materialize_copies_graphml_artifacts(mock_run, mock_load, tmp_path: Path):
    from datetime import UTC, datetime

    graphs_root = tmp_path / "graphs"
    issuer_dir = graphs_root / "AAPL"
    issuer_dir.mkdir(parents=True)
    snapshot_id = "snap-123"
    (issuer_dir / f"{snapshot_id}.graphml").write_text("<graphml/>", encoding="utf-8")
    (issuer_dir / f"{snapshot_id}.manifest.json").write_text("{}", encoding="utf-8")

    member = MagicMock()
    member.status = CorpusMemberStatus.INCLUDED
    member.resolution.accession = "0000320193-24-000123"
    job = MagicMock()
    job.snapshot_id = snapshot_id
    job.members = [member]
    mock_run.return_value = job
    mock_load.return_value = GraphSnapshot(
        snapshot_id=snapshot_id,
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
    draft = tmp_path / "draft"
    bundle, _report = materialize_sampled_corpus(
        sampling, draft, graphs_root=graphs_root, run_id="run1"
    )
    graphml = draft / "corpus" / "graphs" / "AAPL" / f"{snapshot_id}.graphml"
    assert graphml.is_file(), "GraphML must be copied into draft bundle"
    assert bundle.issuer_snapshots[0].snapshot_id == snapshot_id
    assert any(k.endswith(".graphml") for k in bundle.artifact_hashes)


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
    graphs_root = tmp_path / "graphs"
    _seed_graph_files(graphs_root, "AAPL", "snap-123")
    bundle, report = materialize_sampled_corpus(
        sampling, tmp_path, graphs_root=graphs_root, run_id="run1"
    )
    mock_run.assert_called_once()
    assert len(bundle.issuer_snapshots) == 1
    assert report.rejections_by_reason["no_filings_sampled:BAC"] == 1
