"""Corpus materialize with fixtures."""

from ingestion.corpus import materialize_corpus_members
from models.corpus import CorpusDefinition, CorpusDefinitionMode, CorpusMemberStatus


def test_materialize_fixture_corpus():
    defn = CorpusDefinition(
        issuer_id="AAPL",
        mode=CorpusDefinitionMode.EXPLICIT_ACCESSIONS,
        accessions=["0000320193-24-000123", "0000320193-24-000076"],
        max_filings=12,
    )
    job = materialize_corpus_members(defn)
    included = [m for m in job.members if m.status == CorpusMemberStatus.INCLUDED]
    assert len(included) == 2
