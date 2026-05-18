from evaluation.metrics.ranking import compute_ranking_metrics


def test_ndcg_perfect_match():
    m = compute_ranking_metrics(["a", "b"], ["a", "b"])
    assert m.ndcg_at_10 == 1.0
    assert m.mrr == 1.0


def test_mrr_no_match():
    m = compute_ranking_metrics(["x"], ["a"])
    assert m.mrr == 0.0
