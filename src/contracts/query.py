from pydantic import BaseModel, Field

from models.enums import QueryStatus
from models.query import AnswerPackage


class QueryRequest(BaseModel):
    query: str
    snapshot_id: str
    metadata: dict[str, str] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    answer: AnswerPackage | None
    status: QueryStatus
    mlflow_run_id: str
    trajectory_uri: str = ""
