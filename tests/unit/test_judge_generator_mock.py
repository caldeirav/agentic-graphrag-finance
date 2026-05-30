"""Mock judge generation tests (011)."""

from pathlib import Path

from evaluation.generation.config_loader import load_generation_config
from evaluation.generation.judge_generator import generate_items
from models.benchmark_generation import SamplingManifest, SelectedIssuer

REPO = Path(__file__).resolve().parents[2]


def test_mock_judge_generates_profile_tags(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("USE_MOCK_JUDGE", "1")
    config = load_generation_config(REPO / "configs/benchmarks/custom_judge_ci.yaml", base=REPO)
    sampling = SamplingManifest(
        manifest_id="m",
        config_hash="sha256:x",
        allowlist_hash="sha256:y",
        random_seed=0,
        selected_issuers=[
            SelectedIssuer(
                ticker="AAPL",
                accessions=["0000320193-24-000123", "0000320193-24-000076"],
                selection_rationale=["fixture"],
            )
        ],
    )
    (tmp_path / "corpus").mkdir()
    (tmp_path / "corpus" / "graph_node_index.json").write_text(
        '{"paths": ["0000320193-24-000123/Item7", "0000320193-24-000076/Item7"]}'
    )
    accepted, report = generate_items(config, sampling, tmp_path, target_count=3)
    profiles = {item.inspiration_profile for item in accepted}
    assert profiles  # at least one accepted
    assert report.judge_api_calls >= 1
