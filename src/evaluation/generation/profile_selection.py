"""Profile-quota selection for custom-judge dev splits (017)."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from models.benchmark_generation import GeneratedBenchmarkItem


class ProfileSelectionError(ValueError):
    """Raised when the accepted pool cannot satisfy profile quota targets."""


def quota_targets(profile_quotas: dict[str, float], target_count: int) -> dict[str, int]:
    """Allocate integer per-profile targets using largest-remainder rounding."""
    if target_count <= 0:
        msg = "target_count must be positive"
        raise ValueError(msg)
    if not profile_quotas:
        msg = "profile_quotas must not be empty"
        raise ValueError(msg)
    total_weight = sum(max(weight, 0.0) for weight in profile_quotas.values())
    if total_weight <= 0:
        msg = "profile_quotas must include at least one positive weight"
        raise ValueError(msg)

    profiles = list(profile_quotas.keys())
    raw = {profile: target_count * profile_quotas[profile] / total_weight for profile in profiles}
    targets = {profile: int(raw[profile]) for profile in profiles}
    remainder = target_count - sum(targets.values())
    order = sorted(profiles, key=lambda profile: raw[profile] - targets[profile], reverse=True)
    for index in range(remainder):
        targets[order[index % len(order)]] += 1
    return targets


def _selection_key(item_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{item_id}".encode()).hexdigest()


def _rank_pool(
    items: list[GeneratedBenchmarkItem],
    *,
    seed: int,
) -> list[GeneratedBenchmarkItem]:
    return sorted(items, key=lambda item: _selection_key(item.item_id, seed))


def select_profile_balanced_items(
    items: list[GeneratedBenchmarkItem],
    profile_quotas: dict[str, float],
    target_count: int,
    *,
    seed: int = 0,
) -> list[GeneratedBenchmarkItem]:
    """Select ``target_count`` items matching profile quotas (deterministic)."""
    if target_count <= 0:
        msg = "target_count must be positive"
        raise ValueError(msg)
    if len(items) <= target_count:
        return sorted(items, key=lambda item: item.item_id)

    targets = quota_targets(profile_quotas, target_count)
    by_profile: dict[str, list[GeneratedBenchmarkItem]] = defaultdict(list)
    for item in items:
        by_profile[item.inspiration_profile].append(item)

    for profile, target in targets.items():
        available = len(by_profile.get(profile, []))
        if available < target:
            msg = (
                f"Profile selection failed: {profile} needs {target} items "
                f"but only {available} are available in the pool"
            )
            raise ProfileSelectionError(msg)

    selected: list[GeneratedBenchmarkItem] = []
    for profile, target in targets.items():
        pool = _rank_pool(by_profile.get(profile, []), seed=seed)
        selected.extend(pool[:target])

    if len(selected) != target_count:
        msg = f"Profile selection failed: expected {target_count} items, got {len(selected)}"
        raise ProfileSelectionError(msg)
    return sorted(selected, key=lambda item: item.item_id)


def selection_report(
    *,
    pool_count: int,
    selected: list[GeneratedBenchmarkItem],
    targets: dict[str, int],
    seed: int,
) -> dict[str, object]:
    counts = defaultdict(int)
    for item in selected:
        counts[item.inspiration_profile] += 1
    return {
        "pool_count": pool_count,
        "selected_count": len(selected),
        "targets": targets,
        "selected_counts": dict(counts),
        "seed": seed,
    }
