"""Multi-filing issuer corpus and snapshot scope models."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from models.filing import FilingRef

if TYPE_CHECKING:
    from models.ingestion import FilingResolution


class CorpusDefinitionMode(StrEnum):
    DEFAULT_TRAILING = "default_trailing"
    EXPLICIT_ACCESSIONS = "explicit_accessions"
    DATE_RANGE = "date_range"


class CorpusMemberStatus(StrEnum):
    PENDING = "pending"
    INCLUDED = "included"
    FAILED = "failed"
    EXCLUDED = "excluded"


class FiscalPeriodLabel(BaseModel):
    fiscal_year: int
    fiscal_quarter: int | None = None
    label: str = ""

    @classmethod
    def from_filing(
        cls,
        filing: FilingRef,
        *,
        fiscal_year_end_month: int = 12,
    ) -> FiscalPeriodLabel:
        """Map period-of-report to issuer fiscal labels (not calendar quarters by default)."""
        pe = filing.period_end
        fy_end = fiscal_year_end_month
        if filing.form_type.upper().startswith("10-K"):
            fy = pe.year if pe.month <= fy_end else pe.year + 1
            return cls(fiscal_year=fy, fiscal_quarter=None, label=f"FY{fy}")
        if fy_end == 12:
            quarter = (pe.month - 1) // 3 + 1
            fy = pe.year
        else:
            fy = pe.year if pe.month <= fy_end else pe.year + 1
            months_since = (pe.month - fy_end - 1) % 12
            quarter = months_since // 3 + 1
        return cls(fiscal_year=fy, fiscal_quarter=quarter, label=f"FY{fy}-Q{quarter}")


def infer_fiscal_year_end_month(filings: list[FilingRef]) -> int:
    """Infer fiscal year-end month from annual filings in a snapshot or corpus."""
    for ref in filings:
        if ref.form_type.upper().startswith("10-K"):
            return ref.period_end.month
    return 12


class CorpusDefinition(BaseModel):
    issuer_id: str
    mode: CorpusDefinitionMode = CorpusDefinitionMode.DEFAULT_TRAILING
    form_types: list[str] = Field(default_factory=lambda: ["10-K", "10-Q"])
    max_filings: int = 12
    trailing_10k: int = 1
    trailing_10q: int = 4
    accessions: list[str] = Field(default_factory=list)
    period_start: date | None = None
    period_end: date | None = None


class CorpusMember(BaseModel):
    resolution: FilingResolution  # noqa: F821
    fiscal_period: FiscalPeriodLabel | None = None
    status: CorpusMemberStatus = CorpusMemberStatus.PENDING
    failure_reason: str | None = None


class CorpusMaterializationJob(BaseModel):
    job_id: str
    corpus_definition: CorpusDefinition
    members: list[CorpusMember] = Field(default_factory=list)
    snapshot_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class SnapshotIndexEntry(BaseModel):
    snapshot_id: str
    created_at: datetime
    filing_refs: list[FilingRef] = Field(default_factory=list)
    corpus_definition_hash: str = ""


class IssuerSnapshotIndex(BaseModel):
    issuer_id: str
    latest_snapshot_id: str = ""
    versions: list[SnapshotIndexEntry] = Field(default_factory=list)


class CorpusTemporalScope(BaseModel):
    """Structured temporal intent for CLI flags and benchmarks."""

    anchor: str | None = None
    periods: list[str] = Field(default_factory=list)
    compare_periods: list[str] = Field(default_factory=list)
    accessions: list[str] = Field(default_factory=list)
    comparison_mode: str | None = None


class FilingBinding(BaseModel):
    snapshot_id: str
    bound_filings: list[FilingRef] = Field(default_factory=list)
    resolution_notes: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class BoundFilingEntry(BaseModel):
    accession: str
    form_type: str
    fiscal_period: FiscalPeriodLabel
    filed_at: date

    @classmethod
    def from_filing_ref(
        cls,
        ref: FilingRef,
        *,
        fiscal_year_end_month: int = 12,
    ) -> BoundFilingEntry:
        return cls(
            accession=ref.accession,
            form_type=ref.form_type,
            fiscal_period=FiscalPeriodLabel.from_filing(
                ref,
                fiscal_year_end_month=fiscal_year_end_month,
            ),
            filed_at=ref.filed_at,
        )


class SnapshotScopeManifest(BaseModel):
    snapshot_id: str
    issuer_id: str
    bound_filings: list[BoundFilingEntry] = Field(default_factory=list)
    stale_snapshot: bool = False
    newer_available: list[BoundFilingEntry] = Field(default_factory=list)
    excluded_from_binding: list[str] = Field(default_factory=list)
    resolution_notes: list[str] = Field(default_factory=list)


def _rebuild_corpus_models() -> None:
    from models.ingestion import FilingResolution

    CorpusMember.model_rebuild(_types_namespace={"FilingResolution": FilingResolution})


_rebuild_corpus_models()
