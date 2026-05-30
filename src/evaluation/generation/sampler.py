"""Deterministic issuer and filing sampling for custom-judge generation (011)."""

from __future__ import annotations

import hashlib
import json
import random
import uuid
from datetime import UTC, datetime
from pathlib import Path

from evaluation.generation.config_loader import compute_config_hash, load_allowlist
from evaluation.generation.governance import BudgetTracker, GovernanceBudgetExceeded
from models.benchmark_generation import (
    AccessionRecord,
    BudgetSnapshot,
    FilingFilters,
    GenerationConfig,
    IssuerAllowlist,
    SamplingManifest,
    SelectedIssuer,
)


class SamplingError(ValueError):
    """Issuer or filing sample could not satisfy generation config."""


def filter_accessions(
    records: list[AccessionRecord],
    filters: FilingFilters,
    *,
    max_count: int,
) -> list[AccessionRecord]:
    eligible = [
        r
        for r in records
        if r.form_type in filters.form_types
        and filters.min_fiscal_year <= r.fiscal_year <= filters.max_fiscal_year
    ]
    eligible.sort(key=lambda r: (r.filed_at, r.accession), reverse=True)
    return eligible[:max_count]


def _canonical_manifest_body(manifest: SamplingManifest) -> str:
    payload = manifest.model_dump(mode="json")
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sampling_manifest_hash(manifest: SamplingManifest) -> str:
    stable = {
        "config_hash": manifest.config_hash,
        "allowlist_hash": manifest.allowlist_hash,
        "random_seed": manifest.random_seed,
        "selected_issuers": [s.model_dump() for s in manifest.selected_issuers],
        "budget_snapshot": manifest.budget_snapshot.model_dump(),
    }
    digest = hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"sha256:{digest}"


def sample_issuers_and_filings(
    config: GenerationConfig,
    allowlist: IssuerAllowlist,
    accession_catalog: dict[str, list[AccessionRecord]],
    *,
    budget: BudgetTracker | None = None,
) -> SamplingManifest:
    """Seed-random issuer draw with deterministic accession selection."""
    tracker = budget or BudgetTracker(config.governance)
    tracker.preflight_issuers(config.issuer_sample_count)

    rng = random.Random(config.random_seed)
    entries = list(allowlist.entries)
    rng.shuffle(entries)

    selected_issuers: list[SelectedIssuer] = []
    total_filings = 0
    for entry in entries:
        if len(selected_issuers) >= config.issuer_sample_count:
            break
        ticker = entry.ticker.upper()
        pool = accession_catalog.get(ticker, [])
        accessions = filter_accessions(
            pool,
            config.filing_filters,
            max_count=config.filing_filters.max_filings_per_issuer,
        )
        if not accessions:
            continue
        tracker.record_issuer()
        total_filings += len(accessions)
        if total_filings > config.governance.max_filings_per_issuer * config.governance.max_issuers:
            raise GovernanceBudgetExceeded(
                "max_filings_per_issuer",
                config.governance.max_filings_per_issuer * config.governance.max_issuers,
                total_filings,
            )
        selected_issuers.append(
            SelectedIssuer(
                ticker=ticker,
                cik=entry.cik,
                accessions=[a.accession for a in accessions],
                selection_rationale=sorted(entry.sources),
            )
        )

    if len(selected_issuers) < config.issuer_sample_count:
        msg = (
            f"Only {len(selected_issuers)} issuers had eligible filings under "
            f"filing_filters; need {config.issuer_sample_count}. "
            "Widen min_fiscal_year/max_fiscal_year or expand the allowlist."
        )
        raise SamplingError(msg)

    selected_issuers.sort(key=lambda s: s.ticker)
    manifest = SamplingManifest(
        manifest_id=str(uuid.uuid4()),
        config_hash=compute_config_hash(config),
        allowlist_hash=allowlist.content_hash,
        random_seed=config.random_seed,
        selected_issuers=selected_issuers,
        created_at=datetime.now(UTC),
        budget_snapshot=BudgetSnapshot(
            issuers_selected=len(selected_issuers),
            filings_selected=total_filings,
        ),
    )
    return manifest


def write_sampling_manifest(manifest: SamplingManifest, draft_dir: Path) -> str:
    draft_dir.mkdir(parents=True, exist_ok=True)
    path = draft_dir / "sampling_manifest.json"
    path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n")
    return sampling_manifest_hash(manifest)


def run_sampling(
    config_path: Path,
    draft_dir: Path,
    accession_catalog: dict[str, list[AccessionRecord]],
    *,
    repo_root: Path | None = None,
) -> SamplingManifest:
    from evaluation.generation.config_loader import load_generation_config

    root = repo_root or Path(__file__).resolve().parents[2]
    config = load_generation_config(config_path, base=root)
    allowlist = load_allowlist(config.allowlist_path, base=root)
    budget = BudgetTracker(config.governance)
    budget.preflight_issuers(config.issuer_sample_count)
    manifest = sample_issuers_and_filings(
        config,
        allowlist,
        accession_catalog,
        budget=budget,
    )
    write_sampling_manifest(manifest, draft_dir)
    return manifest
