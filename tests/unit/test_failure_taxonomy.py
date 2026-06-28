"""Unit tests for engineering failure taxonomy (019)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.investigation.materialization_audit import build_materialization_audit
from evaluation.reproduction.investigation.taxonomy import (
    ENGINEERING_TO_HUMAN_CLASS,
    default_human_class,
    suggest_failure_class,
)
from models.benchmark_generation import AnswerType, FailureClass, GeneratedBenchmarkItem, GroundTruth
from models.enums import EvidenceSourceType
from models.evaluation import BenchmarkResult, ExpectedBindings, JudgeVerdict, RankingMetrics
from models.investigation import EngineeringFailureClass, MaterializationAudit
from models.query import AnswerPackage, EvidenceChunk


def _item(**kwargs) -> GeneratedBenchmarkItem:
    defaults = {
        "item_id": "v2-test-0001",
        "question": "What was revenue?",
        "question_type_tag": "single-fact",
        "inspiration_profile": "financebench",
        "ground_truth": GroundTruth(answer="$416.16 billion", answer_type=AnswerType.NUMERIC),
        "expected_bindings": ExpectedBindings(accessions=["0000320193-24-000123"]),
        "expected_section_paths": ["0000320193-24-000123/XBRL"],
        "validation_status": "accepted",
    }
    defaults.update(kwargs)
    return GeneratedBenchmarkItem.model_validate(defaults)


def _result(**kwargs) -> BenchmarkResult:
    defaults = {
        "item_id": "v2-test-0001",
        "outcome_score": 0.0,
        "judge_status": "ok",
        "ranking_metrics": RankingMetrics(mrr=1.0, ndcg_at_10=1.0),
    }
    defaults.update(kwargs)
    return BenchmarkResult.model_validate(defaults)


def test_abstention_rule() -> None:
    result = _result(answer=AnswerPackage(text="Insufficient evidence to answer.", citations=[]))
    cls, detail = suggest_failure_class(item=_item(), result=result)
    assert cls == EngineeringFailureClass.ABSTENTION
    assert "insufficient" in detail.lower()


def test_binding_error_from_audit() -> None:
    audit = MaterializationAudit(binding_miss=True)
    result = _result(
        answer=AnswerPackage(
            text="Revenue discussion without binding fix.",
            citations=[
                EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h"),
            ],
        )
    )
    cls, _ = suggest_failure_class(item=_item(), result=result, materialization_audit=audit)
    assert cls == EngineeringFailureClass.BINDING_ERROR


def test_template_dump_rule() -> None:
    answer = AnswerPackage(
        text="Based on 3 evidence chunk(s) from SEC filings:\n[1] ...",
        citations=[EvidenceChunk(chunk_node_id="c1", excerpt="x", content_hash="h")],
    )
    result = _result(
        answer=answer,
        trajectory_snapshot={"synthesis_path": "template"},
    )
    cls, _ = suggest_failure_class(item=_item(), result=result)
    assert cls == EngineeringFailureClass.SYNTHESIS_TEMPLATE_DUMP


def test_numeric_xbrl_miss_rule() -> None:
    answer = AnswerPackage(
        text="The company reported strong performance.",
        citations=[
            EvidenceChunk(
                chunk_node_id="c1",
                excerpt="Revenue 416",
                content_hash="h",
                source_type=EvidenceSourceType.XBRL,
            )
        ],
    )
    cls, _ = suggest_failure_class(item=_item(), result=_result(answer=answer))
    assert cls == EngineeringFailureClass.NUMERIC_XBRL_MISS


def test_engineering_to_human_mapping() -> None:
    assert default_human_class(EngineeringFailureClass.BINDING_ERROR) == FailureClass.AGENT_FAILURE
    assert default_human_class(EngineeringFailureClass.GT_ISSUE_SUSPECTED) == FailureClass.GT_TOO_STRICT
    assert ENGINEERING_TO_HUMAN_CLASS[EngineeringFailureClass.NUMERIC_XBRL_MISS] == FailureClass.AGENT_FAILURE
