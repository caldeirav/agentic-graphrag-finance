from evaluation.registry import default_registry
from evaluation.runner import BenchmarkSuite, EvaluationRunner
from graph.store import save_snapshot
from retrieval.service import QueryService


def test_benchmark_smoke(tmp_path, sample_graph_snapshot):
    save_snapshot(sample_graph_snapshot, tmp_path)
    svc = QueryService(graph_base_dir=tmp_path, issuer_id="0000320193")
    runner = EvaluationRunner(registry=default_registry())
    suite = BenchmarkSuite(datasets=["finder"], split="pilot", max_items=1)
    result = runner.run_suite(
        suite,
        sample_graph_snapshot.snapshot_id,
        svc,
        issuer_id="0000320193",
        report_dir=tmp_path / "reports",
    )
    assert len(result.items) == 1
    assert result.items[0].mlflow_run_id
