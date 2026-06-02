"""Typed view models for reproduction report generation (014)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from models.reproduction import ReproRun


class PaperTableId(StrEnum):
    HEADLINE = "headline"
    BY_PROFILE = "by_profile"
    VARIANT_DELTA = "variant_delta"
    TRAJECTORY_AUDIT = "trajectory_audit"


PAPER_TABLE_IDS: tuple[PaperTableId, ...] = tuple(PaperTableId)
STANDARD_VARIANTS: tuple[str, ...] = (
    "graph-full",
    "flat-chunk",
    "ablation-no-macro",
    "ablation-no-walker",
    "ablation-xbrl-only",
)
PRIMARY_METRICS: tuple[str, ...] = ("outcome_accuracy", "ndcg_at_10", "trajectory_fidelity")

CSV_HEADERS: dict[PaperTableId, tuple[str, ...]] = {
    PaperTableId.HEADLINE: (
        "variant_id",
        "metric_name",
        "value",
        "item_count",
        "excluded_incomplete",
        "excluded_degraded",
        "na_reason",
    ),
    PaperTableId.BY_PROFILE: (
        "variant_id",
        "inspiration_profile",
        "metric_name",
        "value",
        "item_count",
        "excluded_incomplete",
        "excluded_degraded",
        "na_reason",
    ),
    PaperTableId.VARIANT_DELTA: (
        "baseline_variant",
        "comparison_variant",
        "metric_name",
        "delta",
    ),
    PaperTableId.TRAJECTORY_AUDIT: (
        "variant_id",
        "excluded_incomplete",
        "excluded_degraded",
        "excluded_pending_judge",
        "included_in_headline",
    ),
}


class TableData(BaseModel):
    columns: list[str]
    rows: list[dict[str, str]]


class VariantCount(BaseModel):
    variant_id: str
    items_total: int = 0
    excluded_incomplete: int = 0
    excluded_degraded: int = 0
    excluded_pending_judge: int = 0
    has_results: bool = True


class ReproOutputBundle(BaseModel):
    output_dir: Path
    repro_run: ReproRun
    tables: dict[str, TableData]
    variant_results: dict[str, list[ItemResultRecord]] = Field(default_factory=dict)
    release_manifest: dict[str, Any] | None = None
    export_manifest: dict[str, Any] | None = None
    headline_tex: str | None = None
    warnings: list[str] = Field(default_factory=list)
    incomplete_variants: list[str] = Field(default_factory=list)


class RunSummaryView(BaseModel):
    release_tag: str
    repro_run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: float | None = None
    defer_judge: bool = False
    resume_mode: bool = False
    variant_counts: list[VariantCount] = Field(default_factory=list)
    mlflow_links: list[str] = Field(default_factory=list)
    export_manifest_summary: dict[str, Any] | None = None
    manifest_unavailable: bool = False


class PaperTableView(BaseModel):
    table_id: PaperTableId
    columns: list[str]
    rows: list[dict[str, str]]
    latex_copy: str
    csv_copy: str
    markdown_copy: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class VariantMetricSeries(BaseModel):
    variant_id: str
    values_by_metric: dict[str, float]
    delta_vs_baseline: dict[str, float] = Field(default_factory=dict)


class VariantComparisonView(BaseModel):
    metric_names: list[str]
    series: list[VariantMetricSeries]
    baseline_variant: str = "graph-full"


class ItemResultRecord(BaseModel):
    variant_id: str
    item_id: str
    inspiration_profile: str = ""
    judge_status: str = ""
    validation_status: str = ""
    outcome_score: float | None = None
    ndcg_at_10: float | None = None
    trajectory_fidelity: float | None = None
    rubric_scores: dict[str, float] = Field(default_factory=dict)
    structural_metrics: dict[str, float] = Field(default_factory=dict)
    failure_reason: str = ""
    answer_excerpt: str = ""
    citation_count: int = 0
    trajectory_ref: str = ""
    source_path: str = ""
    flags: list[str] = Field(default_factory=list)


class ReportArtifact(BaseModel):
    html_path: Path | None = None
    assets_dir: Path | None = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_hashes: dict[str, str] = Field(default_factory=dict)
    format: str = "html"
