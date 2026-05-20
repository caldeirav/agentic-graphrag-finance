from pydantic import BaseModel, Field

from models.corpus import CorpusTemporalScope
from models.enums import OperationClass
from models.query import AnswerPackage


class GroundTruth(BaseModel):
    answer: str | None = None
    relevant_chunk_ids: list[str] = Field(default_factory=list)
    rubric: str | None = None


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


class RankingMetrics(BaseModel):
    mrr: float | None = None
    map_score: float | None = None
    ndcg_at_10: float | None = None


class JudgeVerdict(BaseModel):
    judge_model: str
    judge_version: str
    rationale: str = ""
    scores: dict[str, float] = Field(default_factory=dict)


class BenchmarkResult(BaseModel):
    item_id: str
    answer: AnswerPackage | None = None
    mlflow_run_id: str = ""
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
