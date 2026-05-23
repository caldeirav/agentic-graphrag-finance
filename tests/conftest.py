"""Pytest fixtures."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import pytest

from graph.builder import build_snapshot
from models.filing import FilingRef, SectionBlock, TableBlock
from models.ingestion import FilingResolution, XBRLArtifact, XBRLArtifactManifest, XBRLArtifactRole
from models.parsing import ParsedDocument
from parsing.docling_xbrl import PARSER_VERSION


@pytest.fixture(autouse=True)
def mock_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("USE_MOCK_LLM", os.environ.get("USE_MOCK_LLM", "1"))
    monkeypatch.setenv("USE_MOCK_JUDGE", os.environ.get("USE_MOCK_JUDGE", "1"))


@pytest.fixture(autouse=True)
def mlflow_run_cleanup() -> None:
    import mlflow

    yield
    while mlflow.active_run() is not None:
        mlflow.end_run()


@pytest.fixture(autouse=True)
def edgar_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "SEC_EDGAR_USER_AGENT",
        os.environ.get("SEC_EDGAR_USER_AGENT", "agentic-graphrag-finance test@example.com"),
    )
    monkeypatch.setenv("USE_FIXTURE_INGESTION", os.environ.get("USE_FIXTURE_INGESTION", "1"))
    downloads = os.environ.get("SEC_DOWNLOADS_ROOT", "data/raw/sec_downloads")
    monkeypatch.setenv("SEC_DOWNLOADS_ROOT", downloads)
    from ingestion import settings

    settings.get_settings.cache_clear()
    yield
    settings.get_settings.cache_clear()


@pytest.fixture
def sample_filing() -> FilingRef:
    return FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        source_uri="fixture://AAPL/0000320193-24-000123",
    )


@pytest.fixture
def sample_parsed_document(sample_filing: FilingRef) -> ParsedDocument:
    return ParsedDocument(
        filing=sample_filing,
        sections=[
            SectionBlock(section_id="sec-1", title="Consolidated Balance Sheets", level=1),
            SectionBlock(section_id="sec-2", title="Management Discussion", level=1),
        ],
        tables=[
            TableBlock(
                table_id="table-0",
                headers=[["", "2024", "2023"]],
                rows=[
                    ["Total assets", "352,583", "323,888"],
                    ["Cash", "29,943", "30,737"],
                ],
            )
        ],
        footnotes=[],
        parse_confidence=0.95,
        parser_version=PARSER_VERSION,
        content_hash="abc123",
    )


@pytest.fixture
def sample_graph_snapshot(sample_parsed_document: ParsedDocument):
    from graph.legacy_builder import build_snapshot as legacy_build_snapshot

    return legacy_build_snapshot(
        "0000320193", [sample_parsed_document], snapshot_id="test-snapshot-001"
    )


@pytest.fixture
def aapl_macro_snapshot():
    """Multi-filing snapshot for macro routing tests (008)."""
    refs = [
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000013",
            form_type="10-Q",
            filed_at=date(2026, 5, 1),
            period_end=date(2026, 3, 28),
            source_uri="u1",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-26-000006",
            form_type="10-Q",
            filed_at=date(2026, 1, 30),
            period_end=date(2025, 12, 27),
            source_uri="u2",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000057",
            form_type="10-Q",
            filed_at=date(2025, 5, 2),
            period_end=date(2025, 6, 28),
            source_uri="u3",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000073",
            form_type="10-Q",
            filed_at=date(2025, 2, 1),
            period_end=date(2025, 3, 29),
            source_uri="u3b",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-25-000079",
            form_type="10-K",
            filed_at=date(2025, 10, 31),
            period_end=date(2025, 9, 27),
            source_uri="u4",
        ),
        FilingRef(
            cik="0000320193",
            accession="0000320193-24-000123",
            form_type="10-K",
            filed_at=date(2024, 11, 1),
            period_end=date(2024, 9, 28),
            source_uri="u5",
        ),
    ]
    docs = [
        ParsedDocument(
            filing=r,
            sections=[],
            tables=[],
            footnotes=[],
            parse_confidence=1.0,
            parser_version="test",
            content_hash=r.accession,
        )
        for r in refs
    ]
    from graph.legacy_builder import build_snapshot as legacy_build_snapshot

    return legacy_build_snapshot("AAPL", docs, snapshot_id="macro-test")


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_downloads_root() -> Path:
    return Path(__file__).parent / "fixtures" / "sec_downloads"


@pytest.fixture
def sample_resolution() -> FilingResolution:
    return FilingResolution(
        ticker="AAPL",
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 11, 1),
        period_end=date(2024, 9, 28),
        edgar_filing_url="fixture://AAPL/0000320193-24-000123",
    )


@pytest.fixture
def sample_manifest(sample_resolution: FilingResolution) -> XBRLArtifactManifest:
    acc = sample_resolution.accession.replace("-", "")
    return XBRLArtifactManifest(
        resolution=sample_resolution,
        artifacts=[
            XBRLArtifact(filename=f"{acc}_htm.xml", role=XBRLArtifactRole.INSTANCE),
            XBRLArtifact(filename=f"{acc}.xsd", role=XBRLArtifactRole.SCHEMA),
        ],
        complete=True,
    )
