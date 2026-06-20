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


class FailureClass(StrEnum):
    GT_TOO_STRICT = "gt_too_strict"
    GT_WRONG = "gt_wrong"
    GT_BOILERPLATE = "gt_boilerplate"
    QUESTION_AMBIGUOUS = "question_ambiguous"
    CLAIMS_MISALIGNED = "claims_misaligned"
    ACCEPTABLE_HARD = "acceptable_hard"
    AGENT_FAILURE = "agent_failure"


class CorpusSpotCheckStatus(StrEnum):
    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"


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
    duplicate_feedback_enabled: bool = True
    max_items_per_issuer_per_profile: int = 8
    min_unique_question_type_tags_per_profile: int = 6
    prompt_negative_examples_count: int = 5


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


class ReproContextSnapshot(BaseModel):
    mrr: float | None = None
    ndcg_at_10: float | None = None
    outcome_score: float | None = None


class ProposedOverrides(BaseModel):
    question: str | None = None
    ground_truth: GroundTruth | None = None
    expected_bindings: ExpectedBindings | None = None
    expected_section_paths: list[str] | None = None


class ItemAnnotation(BaseModel):
    annotation_id: str
    item_id: str
    reviewer_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    failure_class: FailureClass
    notes: str = ""
    corpus_spot_check: CorpusSpotCheckStatus = CorpusSpotCheckStatus.PENDING
    proposed_overrides: ProposedOverrides | None = None
    repro_context: ReproContextSnapshot | None = None


class ReviewQueueEntry(BaseModel):
    item_id: str
    priority_tier: int
    priority_score: float
    mrr: float | None = None
    ndcg_at_10: float | None = None
    outcome_score: float | None = None
    inspiration_profile: str
    question_preview: str
    latest_failure_class: str | None = None


class OverrideChangelogEntry(BaseModel):
    item_id: str
    parent_item_hash: str
    applied_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    reviewer_id: str
    annotation_id: str
    changed_fields: list[str] = Field(default_factory=list)
    rationale: str = ""
    validation_outcome: Literal["accepted", "rejected"]
    validation_errors: list[str] = Field(default_factory=list)


class DuplicateRejectionFeedback(BaseModel):
    rejected_question: str
    matched_item_id: str
    inspiration_profile: str
    issuer_ticker: str
    similarity_score: float
    rejected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProfileDiversityStats(BaseModel):
    unique_issuers: int = 0
    unique_question_type_tags: int = 0
    items_accepted: int = 0


class DiversityReport(BaseModel):
    duplicate_rejection_rate: float = 0.0
    duplicate_rejection_count: int = 0
    candidates_total: int = 0
    by_profile: dict[str, ProfileDiversityStats] = Field(default_factory=dict)
    baseline_reference: str = "v2.0.0"


class QualityPassSummary(BaseModel):
    items_reviewed: int = 0
    items_fixed_override: int = 0
    items_fixed_regenerate: int = 0
    failure_class_counts: dict[str, int] = Field(default_factory=dict)
    dataset_caused_zero_score_count: int = 0
    dataset_caused_zero_score_rate: float = 0.0
    rejudge_improved_count: int = 0
    rejudge_improved_rate: float = 0.0
