"""Unit tests for evidence stratum assignment (015)."""

from evaluation.reproduction.stratum import assign_primary_evidence_source, classify_chunk_id


def test_classify_html_chunk() -> None:
    assert classify_chunk_id("doc-0000320193-24-000123-html-risk_factors-1-body") == "html"
    assert classify_chunk_id("html-item7-mda") == "html"


def test_classify_xbrl_chunk() -> None:
    assert classify_chunk_id("doc-0000320193-24-000123-xbrl-abc123") == "xbrl"


def test_classify_legacy_sec_id_defaults_html() -> None:
    assert classify_chunk_id("sec-risk_factors-1") == "html"


def test_assign_html_only() -> None:
    assert assign_primary_evidence_source(["html-a", "doc-x-html-body"]) == "html"


def test_assign_xbrl_only() -> None:
    assert assign_primary_evidence_source(["doc-x-xbrl-fact"]) == "xbrl"


def test_assign_mixed() -> None:
    ids = ["doc-x-html-body", "doc-x-xbrl-fact"]
    assert assign_primary_evidence_source(ids) == "mixed"


def test_assign_unknown_empty() -> None:
    assert assign_primary_evidence_source([]) == "unknown"
