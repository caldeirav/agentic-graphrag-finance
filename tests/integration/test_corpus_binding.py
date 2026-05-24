"""Binding manifest matches expected accessions."""


from cli.corpus_pipeline import run_materialize_pipeline
from graph.registry import get_latest_snapshot
from models.corpus import CorpusDefinition, CorpusDefinitionMode, CorpusTemporalScope
from retrieval.temporal import bind_filings_for_query


def test_structured_scope_binding(tmp_path):
    graphs = tmp_path / "graphs"
    parsed = tmp_path / "parsed"
    defn = CorpusDefinition(
        issuer_id="AAPL",
        mode=CorpusDefinitionMode.EXPLICIT_ACCESSIONS,
        accessions=["0000320193-24-000123", "0000320193-24-000076"],
    )
    run_materialize_pipeline(defn, ticker="AAPL", graphs_dir=graphs, parsed_dir=parsed)
    snap = get_latest_snapshot("AAPL", graphs)
    scope = CorpusTemporalScope(accessions=["0000320193-24-000076"])
    binding = bind_filings_for_query(scope, snap)
    assert len(binding.bound_filings) == 1
    assert binding.bound_filings[0].accession == "0000320193-24-000076"
