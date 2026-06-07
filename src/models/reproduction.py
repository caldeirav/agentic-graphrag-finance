"""Pydantic models for research reproduction kit (012)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class ReproductionMode(StrEnum):
    LIVE_REEXECUTION = "live_reexecution"


class VariantBackend(StrEnum):
    LANGGRAPH = "langgraph"
    FLAT_CHUNK = "flat_chunk"


class VariantCapabilities(BaseModel):
    disable_macro_router: bool = False
    disable_graph_walker: bool = False
    xbrl_only: bool = False


class ModelPins(BaseModel):
    llm_config_path: str
    llm_config_hash: str
    judge_config_path: str
    judge_config_hash: str
    embedding_model_id: str
    embedding_model_revision: str
    embedding_config_path: str
    embedding_config_hash: str


class ToleranceBands(BaseModel):
    mean_outcome_accuracy: float = 0.02
    mean_rubric_alignment: float = 0.02
    mean_trajectory_fidelity: float = 0.02
    ranking_metrics_exact: bool = True
    structural_metrics_exact: bool = True


class SystemVariantConfig(BaseModel):
    variant_id: str
    description: str
    backend: VariantBackend
    config_path: str | None = None
    top_k: int = 10
    capabilities: VariantCapabilities = Field(default_factory=VariantCapabilities)
    embedding_cache_subdir: str | None = None


PAPER_V1_VARIANT_IDS = (
    "graph-full",
    "flat-chunk",
    "ablation-no-macro",
    "ablation-no-walker",
    "ablation-xbrl-only",
)


class ReleaseManifest(BaseModel):
    schema_version: str = "1.0.0"
    release_tag: str
    git_sha: str
    custom_judge_version: str
    custom_judge_bundle_path: str
    eval_split: str = "dev"
    reproduction_mode: ReproductionMode = ReproductionMode.LIVE_REEXECUTION
    corpus_hashes: dict[str, str] = Field(default_factory=dict)
    relevance_labels_hash: str = ""
    relevance_coverage_rate: float = 0.0
    variant_ids: list[str] = Field(default_factory=list)
    model_pins: ModelPins
    tolerance_bands: ToleranceBands = Field(default_factory=ToleranceBands)
    expected_checksums_path: str = "expected_checksums.json"

    def validate_paper_v1(self) -> None:
        if self.release_tag != "paper-v1.0":
            return
        if list(self.variant_ids) != list(PAPER_V1_VARIANT_IDS):
            msg = f"paper-v1.0 requires variants {PAPER_V1_VARIANT_IDS}, got {self.variant_ids}"
            raise ValueError(msg)
        if self.eval_split != "dev":
            msg = "paper-v1.0 requires eval_split=dev"
            raise ValueError(msg)


class RelevanceFailure(BaseModel):
    item_id: str
    expected_section_paths: list[str] = Field(default_factory=list)
    reason: str


class RelevanceLabelSet(BaseModel):
    labels_hash: str
    snapshot_id: str
    coverage_rate: float
    items_labeled: int
    items_failed: list[RelevanceFailure] = Field(default_factory=list)
    labels_by_item_id: dict[str, list[str]] = Field(default_factory=dict)


class StructuralMetrics(BaseModel):
    accession_binding_accuracy: float = 0.0
    section_path_hit_rate: float = 0.0
    multi_filing_success_rate: float = 0.0


class EvalRunRef(BaseModel):
    variant_id: str
    mlflow_parent_run_id: str = ""
    report_dir: str
    items_excluded_incomplete: int = 0
    items_excluded_degraded: int = 0
    structural_metrics: StructuralMetrics = Field(default_factory=StructuralMetrics)


class DeferJudgeConfig(BaseModel):
    enabled: bool = False
    judge_after: Literal["each_variant", "all_variants"] = "each_variant"
    concurrency: int = 2
    allow_pending_export: bool = False


class ReproRun(BaseModel):
    repro_run_id: str
    release_tag: str
    manifest_hash: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    variant_runs: list[EvalRunRef] = Field(default_factory=list)
    offline_mode: bool = True
    status: Literal["running", "completed", "failed"] = "running"
    defer_judge: bool = False
    current_variant: str = ""
    completed_variants: list[str] = Field(default_factory=list)
    items_completed: dict[str, int] = Field(default_factory=dict)
    judge_phase_status: Literal["not_started", "partial", "complete"] = "not_started"
    last_error: str | None = None


class MetricRow(BaseModel):
    variant_id: str
    metric_name: str
    value: float
    item_count: int
    excluded_incomplete: int = 0
    excluded_degraded: int = 0
    na_reason: str = ""


class ProfileMetricRow(MetricRow):
    inspiration_profile: str


class DeltaRow(BaseModel):
    baseline_variant: str
    comparison_variant: str
    metric_name: str
    delta: float


class StratumMetricRow(MetricRow):
    primary_evidence_source: str
    abstention_rate: float = 0.0


class StratumDeltaRow(BaseModel):
    primary_evidence_source: str
    baseline_variant: str
    comparison_variant: str
    metric_name: str
    delta: float
    baseline_item_count: int = 0
    comparison_item_count: int = 0
    na_reason: str = ""


class AuditRow(BaseModel):
    variant_id: str
    excluded_incomplete: int
    excluded_degraded: int
    excluded_pending_judge: int = 0
    included_in_headline: int


class PaperTableExport(BaseModel):
    release_tag: str
    exported_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    headline_rows: list[MetricRow] = Field(default_factory=list)
    by_profile_rows: list[ProfileMetricRow] = Field(default_factory=list)
    variant_delta_rows: list[DeltaRow] = Field(default_factory=list)
    by_evidence_source_rows: list[StratumMetricRow] = Field(default_factory=list)
    variant_delta_by_source_rows: list[StratumDeltaRow] = Field(default_factory=list)
    audit_rows: list[AuditRow] = Field(default_factory=list)
    stratum_audit: dict[str, int] = Field(default_factory=dict)
