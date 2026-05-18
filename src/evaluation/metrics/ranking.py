"""MRR, MAP, nDCG@k ranking metrics."""

from __future__ import annotations

import math

from models.evaluation import RankingMetrics


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    rel = set(relevant_ids)
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in rel:
            return 1.0 / rank
    return 0.0


def average_precision(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    rel = set(relevant_ids)
    if not rel:
        return 0.0
    hits = 0
    precision_sum = 0.0
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in rel:
            hits += 1
            precision_sum += hits / rank
    return precision_sum / len(rel) if rel else 0.0


def ndcg_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int = 10) -> float:
    rel = set(relevant_ids)
    dcg = sum(
        1.0 / math.log2(rank + 1)
        for rank, rid in enumerate(retrieved_ids[:k], start=1)
        if rid in rel
    )
    ideal_hits = min(len(rel), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return dcg / idcg if idcg > 0 else 0.0


def compute_ranking_metrics(
    retrieved_ids: list[str],
    relevant_ids: list[str],
    *,
    k: int = 10,
) -> RankingMetrics:
    if not relevant_ids:
        return RankingMetrics()
    return RankingMetrics(
        mrr=mrr(retrieved_ids, relevant_ids),
        map_score=average_precision(retrieved_ids, relevant_ids),
        ndcg_at_10=ndcg_at_k(retrieved_ids, relevant_ids, k),
    )
