from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field, computed_field

from models.corpus import CorpusTemporalScope
from models.enums import OperationClass
from models.query import AnswerPackage


class ValidationStatus(StrEnum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    NON_REPRODUCIBLE = "non_reproducible"


class JudgeStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    NOT_EVALUABLE = "not_evaluable"
    PENDING = "pending"


class ValidationReason(BaseModel):
    code: str
    field: str = ""
    message: str = ""


class TrajectoryValidationResult(BaseModel):
    schema_version: str = "1.0.0"
    status: ValidationStatus
    reason_codes: list[ValidationReason] = Field(default_factory=list)
    validated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    snapshot_schema_version: str = ""


class JudgeCriterionResult(BaseModel):
    criterion_id: str
    score: float
    justification: str
    stage: str | None = None


class JudgeRunSummary(BaseModel):
    judge_model: str
    judge_config_id: str
    judge_status: JudgeStatus
    criteria: list[JudgeCriterionResult] = Field(default_factory=list)
    overall_summary: str = ""
    weakest_criterion_id: str | None = None
    weakest_stage: str | None = None
    retry_count: int = 0
    error: str | None = None


class GroundTruth(BaseModel):
    answer: str | None = None
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    rubric: str | None = None
    required_claims: list[str] | None = None


class ExpectedBindings(BaseModel):
    accessions: list[str] = Field(default_factory=list)
    fiscal_periods: list[str] = Field(default_factory=list)


class BenchmarkItem(BaseModel):
    item_id: str
    dataset: str
    question: str
    ground_truth: GroundTruth | None = None
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    operation_class: OperationClass = OperationClass.QUALITATIVE
    temporal_scope: CorpusTemporalScope | None = None
    expected_bindings: ExpectedBindings | None = None
    expected_section_paths: list[str] = Field(default_factory=list)
    multi_filing_required: bool = False
    expect_binding_failure: bool = False


class RankingMetrics(BaseModel):
    mrr: float | None = None
    map_score: float | None = None
    ndcg_at_10: float | None = None


class JudgeVerdict(BaseModel):
    judge_model: str
    judge_version: str
    rationale: str = ""
    scores: dict[str, float] = Field(default_factory=dict)
    criteria: list[JudgeCriterionResult] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def legacy_scores(self) -> dict[str, float]:
        """Map FR-012 criterion ids to legacy benchmark keys."""
        mapping = {
            "synthesis_grounding": "value_alignment",
            "trajectory_coherence": "trajectory_fidelity",
        }
        out = dict(self.scores)
        for new_id, legacy in mapping.items():
            if new_id in self.scores and legacy not in out:
                out[legacy] = self.scores[new_id]
        return out


class BenchmarkResult(BaseModel):
    item_id: str
    answer: AnswerPackage | None = None
    mlflow_run_id: str = ""
    generation_mlflow_run_id: str = ""
    trajectory_snapshot: dict | None = None
    validation_status: str = ""
    judge_status: str = ""
    outcome_score: float = 0.0
    alignment_score: float = 0.0
    trajectory_fidelity: float = 0.0
    ranking_metrics: RankingMetrics | None = None
    judge_verdict: JudgeVerdict | None = None


class EvaluationRun(BaseModel):
    run_id: str
    suite_name: str
    snapshot_id: str
    judge_config_id: str
    items: list[BenchmarkResult] = Field(default_factory=list)
