from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from models.corpus import CorpusDefinition, CorpusTemporalScope, SnapshotScopeManifest


class XBRLArtifactRole(StrEnum):
    INSTANCE = "instance"
    FILING_HTML = "filing_html"
    XBRL_ZIP = "xbrl_zip"
    SCHEMA = "schema"
    CALCULATION = "calculation"
    DEFINITION = "definition"
    LABEL = "label"
    PRESENTATION = "presentation"
    OTHER = "other"


class FetchJobStatus(StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    VALIDATING = "validating"
    COMPLETE = "complete"
    FAILED = "failed"


class IssuerIdentifierInput(BaseModel):
    ticker: str | None = None
    cik: str | None = None
    accession: str | None = None


class FilingResolution(BaseModel):
    ticker: str
    cik: str
    accession: str
    form_type: str
    filed_at: date
    period_end: date
    edgar_filing_url: str = ""


class XBRLArtifact(BaseModel):
    filename: str
    role: XBRLArtifactRole
    url: str = ""
    content_hash: str | None = None


class XBRLArtifactManifest(BaseModel):
    resolution: FilingResolution
    artifacts: list[XBRLArtifact] = Field(default_factory=list)
    complete: bool = False
    html_narrative_status: str = "not_attempted"
    html_artifact_role: str = ""
    html_artifact_relpath: str = ""


class CacheEntry(BaseModel):
    local_path: Path
    manifest_path: Path
    content_hash: str
    parse_ready: bool = False
    cached_at: datetime
    cache_hit: bool = False


class FetchJob(BaseModel):
    job_id: str
    status: FetchJobStatus
    error: str | None = None
    resolution: FilingResolution | None = None


class CLIAskRequest(BaseModel):
    identifier: IssuerIdentifierInput
    query: str
    form_types: list[str] = Field(default_factory=lambda: ["10-K", "10-Q"])
    force_refresh: bool = False
    snapshot_id: str | None = None
    reuse_snapshot_id: str | None = None
    temporal_scope: CorpusTemporalScope | None = None
    corpus_definition: CorpusDefinition | None = None
    force_corpus_refresh: bool = False


class CLIAskResult(BaseModel):
    answer_text: str
    status: str
    mlflow_run_id: str = ""
    snapshot_id: str = ""
    filings_used: list[FilingResolution] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    citations_count: int = 0
    snapshot_scope: SnapshotScopeManifest | None = None


class CLITestResult(BaseModel):
    passed: bool
    node_counts: dict[str, int] = Field(default_factory=dict)
    cache_entry_path: str = ""
    messages: list[str] = Field(default_factory=list)


def _rebuild_cli_ingestion_models() -> None:
    from models.corpus import CorpusDefinition, CorpusTemporalScope, SnapshotScopeManifest

    ns = {
        "CorpusDefinition": CorpusDefinition,
        "CorpusTemporalScope": CorpusTemporalScope,
        "SnapshotScopeManifest": SnapshotScopeManifest,
    }
    CLIAskRequest.model_rebuild(_types_namespace=ns)
    CLIAskResult.model_rebuild(_types_namespace=ns)


_rebuild_cli_ingestion_models()
