from models.enums import EvidenceSourceType, QueryIntent
from models.query import EvidenceChunk
from retrieval.context_budget import (
    budget_for_context_error,
    compact_evidence_for_llm,
    derive_limits,
    is_context_length_error,
    load_context_budget,
    trim_prompt_text,
)


def test_compact_qualitative_risk_limits_chunks_and_chars() -> None:
    evidence = [
        EvidenceChunk(
            chunk_node_id=f"n{i}",
            excerpt="risk factor discussion " * 200,
            content_hash="h",
            source_type=EvidenceSourceType.HTML,
            section_id="html-risk_factors-1",
        )
        for i in range(10)
    ]
    compact = compact_evidence_for_llm(
        evidence,
        query="principal risk factors",
        query_intent=QueryIntent.QUALITATIVE,
    )
    budget = load_context_budget(context_tokens_override=16384)
    assert len(compact) <= budget["max_evidence_chunks"]
    assert all(len(c.excerpt) <= budget["max_excerpt_chars"] + 3 for c in compact)


def test_derive_limits_4096_fits_small_context() -> None:
    limits = derive_limits(4096, 1024)
    assert limits["max_prompt_chars"] <= 12_000
    assert limits["max_evidence_chunks"] <= 10
    # 12 * 1500 would exceed 4096 n_ctx; derived caps must be smaller
    assert limits["max_evidence_chunks"] * limits["max_excerpt_chars"] < 20_000


def test_derive_limits_16384_allows_larger_prompt() -> None:
    limits = derive_limits(16384, 3072)
    assert limits["max_prompt_chars"] >= 30_000
    assert limits["max_evidence_chunks"] >= 8


def test_yaml_caps_cannot_exceed_derived_safe_limits() -> None:
    budget = load_context_budget(context_tokens_override=4096)
    assert budget["max_prompt_chars"] <= 12_000


def test_is_context_length_error() -> None:
    err = Exception(
        "Error code: 400 - {'error': 'n_keep: 6706>= n_ctx: 4096. Try to load the model with a larger context length.'}"
    )
    assert is_context_length_error(err)


def test_budget_for_context_error_parses_n_ctx() -> None:
    err = Exception("n_keep: 6706>= n_ctx: 4096")
    budget = budget_for_context_error(err)
    assert budget is not None
    assert budget["context_tokens"] == 4096
    assert budget["max_prompt_chars"] <= 12_000


def test_trim_prompt_text() -> None:
    long = "x" * 20_000
    out = trim_prompt_text(long, max_chars=1000)
    assert len(out) <= 1000
    assert out.endswith("...[truncated]")
