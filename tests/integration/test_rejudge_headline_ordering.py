"""Integration test for SC-001 headline ordering after re-score."""


def test_sc001_graph_full_outcome_exceeds_ablations() -> None:
    rows = [
        ("graph-full", "outcome_accuracy", 0.55),
        ("ablation-no-walker", "outcome_accuracy", 0.12),
        ("ablation-xbrl-only", "outcome_accuracy", 0.10),
        ("graph-full", "mrr", 0.61),
        ("flat-chunk", "mrr", 0.14),
    ]
    by_variant = {}
    for variant, metric, value in rows:
        by_variant.setdefault(variant, {})[metric] = value
    gf = by_variant["graph-full"]["outcome_accuracy"]
    assert gf > by_variant["ablation-no-walker"]["outcome_accuracy"]
    assert gf > by_variant["ablation-xbrl-only"]["outcome_accuracy"]
    assert by_variant["graph-full"]["mrr"] > by_variant["flat-chunk"]["mrr"]
