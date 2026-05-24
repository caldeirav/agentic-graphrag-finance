"""Integration: multi-filing corpus materialize pipeline."""


from cli.corpus_pipeline import run_materialize_pipeline
from graph.registry import get_latest_snapshot
from graph.registry import load_index as load_snapshot_index
from models.corpus import CorpusDefinition, CorpusDefinitionMode


def test_materialize_pipeline_fixture(tmp_path):
    graphs = tmp_path / "graphs"
    parsed = tmp_path / "parsed"
    defn = CorpusDefinition(
        issuer_id="AAPL",
        mode=CorpusDefinitionMode.EXPLICIT_ACCESSIONS,
        accessions=["0000320193-24-000123", "0000320193-24-000076"],
    )
    job = run_materialize_pipeline(defn, ticker="AAPL", graphs_dir=graphs, parsed_dir=parsed)
    assert job.snapshot_id
    snap = get_latest_snapshot("AAPL", graphs)
    assert snap is not None
    assert len(snap.manifest.filing_refs) == 2
    index = load_snapshot_index("AAPL", graphs)
    assert index.latest_snapshot_id == job.snapshot_id
