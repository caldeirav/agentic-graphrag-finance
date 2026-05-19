from datetime import date, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


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


class CLIAskResult(BaseModel):
    answer_text: str
    status: str
    mlflow_run_id: str = ""
    snapshot_id: str = ""
    filings_used: list[FilingResolution] = Field(default_factory=list)
    timings_ms: dict[str, int] = Field(default_factory=dict)
    citations_count: int = 0


class CLITestResult(BaseModel):
    passed: bool
    node_counts: dict[str, int] = Field(default_factory=dict)
    cache_entry_path: str = ""
    messages: list[str] = Field(default_factory=list)
