"""Integration: ask with temporal scope on multi-filing snapshot."""

from pathlib import Path as StdPath

from cli.corpus_pipeline import run_ask_pipeline, run_materialize_pipeline
from models.corpus import CorpusDefinition, CorpusDefinitionMode, CorpusTemporalScope
from models.ingestion import CLIAskRequest, IssuerIdentifierInput


def test_ask_prior_quarter_binding(tmp_path, monkeypatch):
    graphs = tmp_path / "graphs"
    parsed = tmp_path / "parsed"
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path / 'mlflow.db'}")
    defn = CorpusDefinition(
        issuer_id="AAPL",
        mode=CorpusDefinitionMode.EXPLICIT_ACCESSIONS,
        accessions=["0000320193-24-000123", "0000320193-24-000076"],
    )
    job = run_materialize_pipeline(defn, ticker="AAPL", graphs_dir=graphs, parsed_dir=parsed)

    req = CLIAskRequest(
        identifier=IssuerIdentifierInput(ticker="AAPL"),
        query="Revenue in the prior quarter?",
        temporal_scope=CorpusTemporalScope(anchor="prior_quarter"),
        reuse_snapshot_id=job.snapshot_id,
    )
    _orig = StdPath

    def _path(*parts):
        if parts == ("data/graphs",):
            return graphs
        if parts == ("data/parsed",):
            return parsed
        return _orig(*parts)

    monkeypatch.setattr("cli.corpus_pipeline.Path", _path)
    result = run_ask_pipeline(req)
    assert result.snapshot_scope is not None
    assert len(result.snapshot_scope.bound_filings) >= 1
    assert result.snapshot_scope.bound_filings[0].form_type == "10-Q"
