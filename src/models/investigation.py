"""Pydantic models for agent failure investigation (019)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class EngineeringFailureClass(StrEnum):
    BINDING_ERROR = "binding_error"
    RETRIEVAL_LABEL_MISMATCH = "retrieval_label_mismatch"
    SYNTHESIS_TEMPLATE_DUMP = "synthesis_template_dump"
    NUMERIC_XBRL_MISS = "numeric_xbrl_miss"
    COMPARISON_NARRATIVE_MISS = "comparison_narrative_miss"
    ABSTENTION = "abstention"
    GT_ISSUE_SUSPECTED = "gt_issue_suspected"


class CitationExcerpt(BaseModel):
    chunk_node_id: str = ""
    accession: str = ""
    section_id: str = ""
    excerpt: str = ""


class EdgarFilingLink(BaseModel):
    accession: str
    form_type: str = ""
    period_end: date | None = None
    url: str = ""
    link_omitted_reason: str = ""


class CorpusExcerptSource(StrEnum):
    BUNDLE_SECTION = "bundle_section"
    POINTER = "pointer"


class CorpusExcerpt(BaseModel):
    section_path: str
    text: str
    source: CorpusExcerptSource = CorpusExcerptSource.POINTER


class MaterializationAudit(BaseModel):
    snapshot_id: str = ""
    expected_accessions: list[str] = Field(default_factory=list)
    visited_accessions: list[str] = Field(default_factory=list)
    expected_section_paths: list[str] = Field(default_factory=list)
    visited_section_paths: list[str] = Field(default_factory=list)
    cited_chunk_node_ids: list[str] = Field(default_factory=list)
    binding_miss: bool = False


class FailureInvestigationRow(BaseModel):
    item_id: str
    priority_tier: int | None = None
    priority_score: float | None = None
    inspiration_profile: str = ""
    question: str = ""
    expected_answer: str = ""
    required_claims: list[str] = Field(default_factory=list)
    expected_section_paths: list[str] = Field(default_factory=list)
    agent_answer: str = ""
    citation_excerpts: list[CitationExcerpt] = Field(default_factory=list)
    outcome_score: float | None = None
    mrr: float | None = None
    ndcg_at_10: float | None = None
    judge_status: str = ""
    judge_rationale: str = ""
    judge_scores: dict[str, float] = Field(default_factory=dict)
    synthesis_path: str = ""
    suggested_failure_class: EngineeringFailureClass | None = None
    suggested_failure_detail: str = ""
    human_failure_class: str = ""
    human_annotation_notes: str = ""
    edgar_links: list[EdgarFilingLink] = Field(default_factory=list)
    corpus_excerpts: list[CorpusExcerpt] = Field(default_factory=list)
    materialization_audit: MaterializationAudit | None = None
    graph_context_href: str = ""
    graph_context_inline: bool = False
    repro_result_path: str = ""
    repro_missing: bool = False


class Tier1CohortEntry(BaseModel):
    item_id: str
    priority_tier: int = 1
    priority_score: float = 0.0


class Tier1CohortFile(BaseModel):
    schema_version: str = "1.0.0"
    source_queue_path: str
    source_queue_hash: str
    exported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    item_ids: list[str] = Field(default_factory=list)
    entries: list[Tier1CohortEntry] = Field(default_factory=list)


class CohortDebugMode(StrEnum):
    RERUN = "rerun"
    REPLAY = "replay"


class CohortDebugSummary(BaseModel):
    item_id: str
    variant_id: str = "graph-full"
    mode: CohortDebugMode = CohortDebugMode.RERUN
    macro_plan_summary: str = ""
    filing_set: list[str] = Field(default_factory=list)
    meso_decisions: list[str] = Field(default_factory=list)
    micro_evidence_count: int = 0
    synthesis_path: str = ""
    citation_count: int = 0
    outcome_score: float | None = None
    weakest_judge_criterion: str = ""
    suggested_failure_class: EngineeringFailureClass | None = None
    failure_flags: list[str] = Field(default_factory=list)
    trace_event_count: int = 0


class CohortGateThresholds(BaseModel):
    baseline_snapshot_path: str = ""
    max_strong_retrieval_zero_outcome: int = 63
    max_mrr_ok_va_zero: int = 10
    min_synthesis_template_dump_share_reduction: float = 0.15
    require_regression_suite_pass: bool = True


class CohortBaselineComparison(BaseModel):
    baseline_strong_retrieval_zero_count: int = 0
    delta_strong_retrieval_zero_count: int = 0
    delta_percent: float = 0.0


class CohortValidationReport(BaseModel):
    schema_version: str = "1.0.0"
    cohort_hash: str = ""
    manifest_tag: str = ""
    run_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    output_dir: str = ""
    item_count: int = 0
    tier1_zero_count: int = 0
    strong_retrieval_zero_count: int = 0
    synthesis_path_counts: dict[str, int] = Field(default_factory=dict)
    engineering_failure_counts: dict[str, int] = Field(default_factory=dict)
    mrr_ok_va_zero_count: int = 0
    thresholds: CohortGateThresholds = Field(default_factory=CohortGateThresholds)
    baseline_comparison: CohortBaselineComparison | None = None
    passed: bool = False
    failed_thresholds: list[str] = Field(default_factory=list)
    regression_suite_passed: bool | None = None


class CohortGateOverrideRecord(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    operator: str = ""
    manifest_tag: str = ""
    failed_thresholds: list[str] = Field(default_factory=list)
    rationale: str = ""
