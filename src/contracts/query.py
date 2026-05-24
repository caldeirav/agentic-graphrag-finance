from pydantic import BaseModel, Field

from models.enums import QueryStatus
from models.filing import FilingRef
from models.query import AnswerPackage


class QueryRequest(BaseModel):
    query: str
    snapshot_id: str
    metadata: dict[str, str] = Field(default_factory=dict)
    pre_bound_filings: list[FilingRef] = Field(default_factory=list)


class QueryResponse(BaseModel):
    answer: AnswerPackage | None
    status: QueryStatus
    mlflow_run_id: str
    trajectory_uri: str = ""
    query_id: str = ""
    validation_status: str = ""
    judge_status: str = ""
    judge_scores: dict[str, float] = Field(default_factory=dict)
