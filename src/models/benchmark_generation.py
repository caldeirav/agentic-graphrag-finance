"""Pydantic models for judge-generated custom benchmark datasets (011)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from models.enums import OperationClass
from models.evaluation import ExpectedBindings, GroundTruth


class DatasetStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class AnswerType(StrEnum):
    NUMERIC = "numeric"
    SHORT_LABEL = "short_label"
    NARRATIVE = "narrative"
    COMPARISON_STRUCTURED = "comparison_structured"


class AllowlistEntry(BaseModel):
    ticker: str
    cik: str | None = None
    sources: list[str] = Field(default_factory=list)


class IssuerAllowlist(BaseModel):
    allowlist_id: str
    content_hash: str
    entries: list[AllowlistEntry]
    provenance: str


class FilingFilters(BaseModel):
    form_types: list[str]
    min_fiscal_year: int
    max_fiscal_year: int
    max_filings_per_issuer: int


class GovernanceCaps(BaseModel):
    max_issuers: int
    max_filings_per_issuer: int
    max_items: int
    max_judge_api_calls: int
    max_storage_bytes: int
    max_wall_clock_seconds: int
    validation_pass_rate: float
    dedup_similarity_threshold: float
    judge_retries_per_item: int
    multi_filing_min: int = 0


class OutputPaths(BaseModel):
    drafts_root: str
    published_root: str


class GenerationConfig(BaseModel):
    config_id: str
    bundle_schema_version: str = "1.0.0"
    random_seed: int
    allowlist_id: str
    allowlist_path: str
    issuer_sample_count: int
    filing_filters: FilingFilters
    profile_quotas: dict[str, float]
    inspiration_profile_paths: dict[str, str]
    generation_judge_version: str
    generation_judge_config: str
    evaluation_judge_version: str
    evaluation_judge_config: str
    governance: GovernanceCaps
    output: OutputPaths

    @field_validator("profile_quotas")
    @classmethod
    def quotas_non_empty(cls, value: dict[str, float]) -> dict[str, float]:
        if not value:
            msg = "profile_quotas must not be empty"
            raise ValueError(msg)
        return value


class AccessionRecord(BaseModel):
    accession: str
    form_type: str
    fiscal_year: int
    filed_at: str


class BudgetSnapshot(BaseModel):
    issuers_selected: int = 0
    filings_selected: int = 0
    judge_api_calls: int = 0
    storage_bytes: int = 0
    items_accepted: int = 0


class SelectedIssuer(BaseModel):
    ticker: str
    cik: str | None = None
    accessions: list[str] = Field(default_factory=list)
    selection_rationale: list[str] = Field(default_factory=list)


class SamplingManifest(BaseModel):
    manifest_id: str
    config_hash: str
    allowlist_hash: str
    random_seed: int
    selected_issuers: list[SelectedIssuer]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    budget_snapshot: BudgetSnapshot = Field(default_factory=BudgetSnapshot)


class IssuerSnapshotRef(BaseModel):
    ticker: str
    snapshot_id: str
    relative_path: str


class CorpusBundle(BaseModel):
    snapshot_id: str
    issuer_snapshots: list[IssuerSnapshotRef]
    corpus_root: str
    graph_node_index_path: str
    reachability_audit_path: str | None = None
    total_bytes: int
    artifact_hashes: dict[str, str] = Field(default_factory=dict)


class GeneratedBenchmarkItem(BaseModel):
    item_id: str
    dataset: str = "custom-judge"
    question: str
    question_type_tag: str
    answer_type: AnswerType | None = None
    inspiration_profile: Literal["financebench", "finder", "finagentbench"]
    ground_truth: GroundTruth
    expected_bindings: ExpectedBindings
    expected_section_paths: list[str]
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    multi_filing_required: bool = False
    operation_class: OperationClass = OperationClass.QUALITATIVE
    validation_status: Literal["accepted", "rejected"] = "accepted"
    validation_errors: list[str] = Field(default_factory=list)
    path_repair_version: str | None = None
    suppress_benchmark_path_injection: bool = False


class DatasetManifest(BaseModel):
    schema_version: str = "1.0.0"
    dataset_name: str = "custom-judge"
    version: str
    status: DatasetStatus
    parent_version: str | None = None
    item_count: int
    items_hash: str
    sampling_manifest_path: str
    generation_config_path: str
    generation_report_path: str | None = None
    corpus_bundle: CorpusBundle
    generation_judge_version: str
    evaluation_judge_version: str
    profile_counts: dict[str, int]
    published_at: datetime | None = None
    published_by: str | None = None
    relevance_labels_hash: str | None = None
    relevance_coverage_rate: float | None = None
    relevance_snapshot_id: str | None = None
    relevance_labels_path: str | None = None
    publish_audit_path: str | None = None


class PublishAuditRecord(BaseModel):
    audit_sample_size: int = 20
    audit_sample_item_ids: list[str] = Field(default_factory=list)
    operator_id: str
    signed_off_at: datetime
    feasibility_report_hash: str | None = None
    scorability_report_hash: str | None = None


class GenerationReport(BaseModel):
    run_id: str
    candidates_total: int
    accepted_count: int
    rejected_count: int
    pass_rate: float
    rejections_by_reason: dict[str, int] = Field(default_factory=dict)
    judge_api_calls: int
    storage_bytes_used: int
    duration_seconds: float
    budget_exceeded: bool = False
