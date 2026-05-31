"""Resume and retry tests for judge generation (011)."""

from pathlib import Path

import httpx
import pytest

from evaluation.generation.config_loader import load_generation_config
from evaluation.generation.gemini_item_generator import GeminiItemGenerator
from evaluation.generation.judge_generator import _load_checkpoint, generate_items
from models.benchmark_generation import SamplingManifest, SelectedIssuer

REPO = Path(__file__).resolve().parents[2]


def _sampling() -> SamplingManifest:
    return SamplingManifest(
        manifest_id="m",
        config_hash="sha256:x",
        allowlist_hash="sha256:y",
        random_seed=0,
        selected_issuers=[
            SelectedIssuer(
                ticker="AAPL",
                accessions=["0000320193-24-000123"],
                selection_rationale=["fixture"],
            )
        ],
    )


def _seed_corpus(tmp_path: Path) -> None:
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "graph_node_index.json").write_text(
        '{"paths": ["0000320193-24-000123/Item7"]}'
    )


def test_resume_from_candidates_checkpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    config = load_generation_config(REPO / "configs/benchmarks/custom_judge_ci.yaml", base=REPO)
    _seed_corpus(tmp_path)
    sampling = _sampling()

    _, report1 = generate_items(config, sampling, tmp_path, target_count=2)
    assert report1.candidates_total == 2
    assert len(_load_checkpoint(tmp_path / "candidates.jsonl")) == 2

    _, report2 = generate_items(config, sampling, tmp_path, target_count=3)
    assert report2.candidates_total == 3
    assert len(_load_checkpoint(tmp_path / "candidates.jsonl")) == 3


def test_gemini_generate_retries_transport_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    config = load_generation_config(REPO / "configs/benchmarks/custom_judge_ci.yaml", base=REPO)
    gen = GeminiItemGenerator(config, repo_root=REPO)
    calls = {"n": 0}

    class FakeLLM:
        def invoke(self, _messages):
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
            from langchain_core.messages import AIMessage

            return AIMessage(
                content=(
                    '{"question":"Q?","question_type_tag":"t","ground_truth":{"answer":"A"},'
                    '"expected_bindings":{"accessions":["0000320193-24-000123"],"fiscal_periods":[]},'
                    '"expected_section_paths":["0000320193-24-000123/Item7"],'
                    '"multi_filing_required":false,"operation_class":"QUALITATIVE"}'
                )
            )

    monkeypatch.setattr(
        "evaluation.generation.gemini_item_generator.ChatGoogleGenerativeAI",
        lambda *args, **kwargs: FakeLLM(),
    )
    monkeypatch.setattr("evaluation.generation.api_retry.time.sleep", lambda _: None)

    item, _ = gen.generate_one(
        profile="financebench",
        seq=1,
        sampling=_sampling(),
        section_paths=["0000320193-24-000123/Item7"],
    )
    assert item.question == "Q?"
    assert calls["n"] == 3
