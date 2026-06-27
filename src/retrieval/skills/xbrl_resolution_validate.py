"""Post-selection XBRL resolution validation (023 M3)."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.temporal_scope import TemporalScopeIntent, xbrl_period_matches_intent
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, forbidden_concept_hints, query_concept_family
from retrieval.skills.xbrl_fact_catalog import XbrlFactCatalogEntry
from retrieval.skills.xbrl_fact_resolution import XbrlFactResolutionResult
from retrieval.skills.xbrl_resolution_prompt import min_facts_required
from retrieval.skills.ratio_entry_roles import assign_ratio_pair_for_query
from retrieval.skills.xbrl_taxonomy_catalog import XbrlFactCatalogEntryV2, enrich_catalog_entry


class ValidatedXbrlResolution(BaseModel):
    resolution: XbrlFactResolutionResult
    selected_concepts: list[str] = Field(default_factory=list)
    validation_rejections: list[str] = Field(default_factory=list)


def _catalog_by_id(
    catalog: list[XbrlFactCatalogEntry | XbrlFactCatalogEntryV2],
) -> dict[str, XbrlFactCatalogEntry | XbrlFactCatalogEntryV2]:
    return {entry.chunk_id: entry for entry in catalog}


def _as_v2(entry: XbrlFactCatalogEntry | XbrlFactCatalogEntryV2) -> XbrlFactCatalogEntryV2:
    if isinstance(entry, XbrlFactCatalogEntryV2):
        return entry
    return enrich_catalog_entry(entry)


def _forbidden_hit(concept: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if pattern and pattern.lower() in concept.lower():
            return pattern
        if pattern and re.search(re.escape(pattern), concept, re.I):
            return pattern
    return None


def validate_xbrl_resolution(
    resolution: XbrlFactResolutionResult,
    catalog: list[XbrlFactCatalogEntry | XbrlFactCatalogEntryV2],
    query: str,
    *,
    metric_intent: MetricIntent | None = None,
    temporal_intent: TemporalScopeIntent | None = None,
) -> ValidatedXbrlResolution:
    """Apply concept guards and period checks after LLM/heuristic selection."""
    rejections: list[str] = []
    by_id = _catalog_by_id(catalog)
    guard_family = query_concept_family(query, metric_intent)
    forbidden = forbidden_concept_hints(query, metric_intent)

    selected = [cid for cid in resolution.selected_chunk_ids if cid in by_id]
    selected_entries = [_as_v2(by_id[cid]) for cid in selected]
    selected_concepts = [entry.concept for entry in selected_entries]

    needed = min_facts_required(metric_intent)
    if resolution.sufficient and len(selected) < needed:
        rejections.append(f"Need {needed} facts; got {len(selected)}.")

    for entry in selected_entries:
        seg = bool(entry.segment_hint)
        if guard_family and not concept_passes_guard(
            entry.concept,
            guard_family,
            segment_in_excerpt=seg,
        ):
            rejections.append(f"Concept {entry.concept} fails {guard_family} guard.")
        hit = _forbidden_hit(entry.concept, forbidden)
        if hit:
            rejections.append(f"Concept {entry.concept} matches forbidden pattern {hit}.")
        if temporal_intent and not xbrl_period_matches_intent(
            period_start=entry.period_start,
            period_end=entry.period_end,
            is_annual=entry.is_annual,
            intent=temporal_intent,
        ):
            rejections.append(
                f"Concept {entry.concept} period {entry.period_end} mismatches fiscal intent."
            )
        if (
            temporal_intent
            and temporal_intent.form_preference == "10-K"
            and temporal_intent.target_fiscal_year
            and not entry.is_annual
            and entry.period_end
            and str(temporal_intent.target_fiscal_year) not in entry.period_end[:4]
        ):
            rejections.append(
                f"Concept {entry.concept} is interim; FY{temporal_intent.target_fiscal_year} "
                "annual fact required."
            )

    if (
        metric_intent
        and metric_intent.metric_type == "ratio"
        and len(selected_entries) == 2
    ):
        pair = assign_ratio_pair_for_query(selected_entries, query, metric_intent)
        if pair is None:
            rejections.append("Could not assign numerator and denominator roles for ratio pair.")
            num, den = selected_entries[0], selected_entries[1]
        else:
            num, den = pair
            if [num.chunk_id, den.chunk_id] != selected:
                selected = [num.chunk_id, den.chunk_id]
                selected_entries = [num, den]
                selected_concepts = [num.concept, den.concept]
        if num.period_end and den.period_end and num.period_end != den.period_end:
            rejections.append(
                f"Ratio facts use different periods ({num.period_end} vs {den.period_end})."
            )
        if guard_family == "margin":
            num_roles = set(num.metric_roles)
            if "net_income" not in num_roles:
                if "pretax_income" in num_roles:
                    rejections.append(
                        f"Margin numerator {num.concept} is pretax; use net_income role instead."
                    )
                elif any(
                    token in (num.standard_label or "").lower()
                    for token in ("before income tax", "pretax", "pre-tax")
                ):
                    rejections.append(
                        f"Margin numerator {num.concept} label indicates pretax income."
                    )
                net_alts = [
                    entry
                    for entry in catalog
                    if entry.chunk_id not in selected
                    and entry.period_end == num.period_end
                    and entry.is_annual == num.is_annual
                    and "net_income" in _as_v2(entry).metric_roles
                ]
                if net_alts:
                    rejections.append(
                        f"Margin numerator {num.concept} lacks net_income; "
                        f"catalog has net income alternative for period {num.period_end}."
                    )
                if num.calc_children and any(
                    child.startswith(("ProfitLoss", "NetIncome"))
                    for child in num.calc_children
                ):
                    rejections.append(
                        f"Margin numerator {num.concept} calc_children include net income; "
                        "use net income fact instead."
                    )
            if not any(
                role in den.metric_roles for role in ("revenue", "total_revenue", "margin_denominator")
            ):
                rejections.append(
                    f"Margin denominator {den.concept} lacks revenue/total_revenue role."
                )

    if guard_family == "segment_revenue" and selected_entries:
        from retrieval.skills.xbrl_fact_catalog import _segment_query_name

        segment_query = _segment_query_name(query)
        for entry in selected_entries:
            seg_label = entry.segment_hint or entry.segment_dimension or ""
            if segment_query and (not seg_label or segment_query.lower() not in seg_label.lower()):
                rejections.append(
                    f"Concept {entry.concept} is not segment revenue for {segment_query}."
                )

    if rejections:
        abstain = "; ".join(dict.fromkeys(rejections))
        updated = resolution.model_copy(
            update={
                "selected_chunk_ids": selected,
                "sufficient": False,
                "rationale": resolution.rationale or abstain,
                "selected_concepts": selected_concepts,
                "validation_rejections": rejections,
                "abstain_reason": abstain,
            }
        )
        return ValidatedXbrlResolution(
            resolution=updated,
            selected_concepts=selected_concepts,
            validation_rejections=rejections,
        )

    updated = resolution.model_copy(
        update={
            "selected_chunk_ids": selected,
            "selected_concepts": selected_concepts,
            "validation_rejections": [],
            "abstain_reason": "",
        }
    )
    return ValidatedXbrlResolution(
        resolution=updated,
        selected_concepts=selected_concepts,
        validation_rejections=[],
    )
