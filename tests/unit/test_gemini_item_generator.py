"""Unit tests for live Gemini item generator (011)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evaluation.generation.config_loader import load_generation_config
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from models.benchmark_generation import SamplingManifest, SelectedIssuer

REPO = Path(__file__).resolve().parents[2]
LIVE_CONFIG = REPO / "configs/benchmarks/custom_judge_live.yaml"


def test_live_config_loads():
    config = load_generation_config(LIVE_CONFIG, base=REPO)
    assert config.config_id == "custom_judge_live"
    assert config.governance.max_items == 2


def test_require_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
            GeminiItemGenerator.require_api_key()


@patch("evaluation.generation.gemini_item_generator.ChatGoogleGenerativeAI")
def test_generate_one_parses_json(mock_llm_cls, monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    config = load_generation_config(LIVE_CONFIG, base=REPO)
    sampling = SamplingManifest(
        manifest_id="m",
        config_hash="sha256:x",
        allowlist_hash="sha256:y",
        random_seed=42,
        selected_issuers=[
            SelectedIssuer(
                ticker="AAPL",
                accessions=["0000320193-24-000123"],
                selection_rationale=["fixture"],
            )
        ],
    )
    payload = {
        "question": "What were net sales in the latest 10-K?",
        "question_type_tag": "metrics-generated",
        "ground_truth": {"answer": "391B", "rubric": None},
        "expected_bindings": {
            "accessions": ["0000320193-24-000123"],
            "fiscal_periods": ["FY2024"],
        },
        "expected_section_paths": ["0000320193-24-000123/Item7"],
        "multi_filing_required": False,
        "operation_class": "QUALITATIVE",
    }
    mock_resp = MagicMock()
    mock_resp.content = json.dumps(payload)
    mock_llm_cls.return_value.invoke.return_value = mock_resp

    gen = GeminiItemGenerator(config, repo_root=REPO)
    item, duration_ms = gen.generate_one(
        profile="financebench",
        seq=1,
        sampling=sampling,
        section_paths=["0000320193-24-000123/Item7"],
    )
    assert item.question.startswith("What were net sales")
    assert item.expected_section_paths == ["0000320193-24-000123/Item7"]
    assert duration_ms >= 0
    mock_llm_cls.assert_called_once()
