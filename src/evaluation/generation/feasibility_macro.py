"""Macro-bindability feasibility checks for custom-judge v2.0 bundles (017)."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.reproduction.snapshot_loader import load_bundle_snapshot
from models.benchmark_generation import GeneratedBenchmarkItem
from models.filing import FilingRef
from models.graph import GraphSnapshot
from retrieval.macro.models import MacroBindingProposal, ProposalSource, ValidationStatus
from retrieval.macro.validator import validate_macro_binding


def filing_refs_for_accessions(
    accessions: list[str],
    snapshot: GraphSnapshot,
) -> tuple[list[FilingRef], list[str]]:
    """Resolve full FilingRef rows from snapshot manifest (cli_bound needs all fields)."""
    by_accession = {ref.accession: ref for ref in snapshot.manifest.filing_refs}
    resolved: list[FilingRef] = []
    missing: list[str] = []
    for acc in accessions:
        ref = by_accession.get(acc)
        if ref is None:
            missing.append(acc)
        else:
            resolved.append(ref)
    return resolved, missing


def check_item_macro_bindable(
    item: GeneratedBenchmarkItem,
    snapshot: GraphSnapshot,
) -> tuple[bool, str]:
    """Return (ok, detail) after validating expected_bindings against bundled snapshot."""
    accessions = list(dict.fromkeys(item.expected_bindings.accessions))
    if not accessions:
        return False, "missing accessions"
    cli_bound, missing = filing_refs_for_accessions(accessions, snapshot)
    if missing:
        return False, f"accessions not in corpus manifest: {', '.join(missing)}"
    proposal = MacroBindingProposal(
        intent_summary="benchmark item expected_bindings",
        proposed_accessions=accessions,
        proposal_source=ProposalSource.DETERMINISTIC,
    )
    result = validate_macro_binding(
        proposal,
        snapshot,
        cli_bound=cli_bound,
        query=item.question,
    )
    if result.status != ValidationStatus.APPROVED:
        detail = result.rationale or "; ".join(result.failure_codes)
        return False, detail
    return True, ""


def audit_macro_bindability(
    bundle_root: Path,
    items: list[GeneratedBenchmarkItem],
) -> dict[str, object]:
    """Run macro-bindability gate for all items; returns failure list."""
    manifest_path = bundle_root / "manifest.json"
    issuer_refs: list[object] = []
    if manifest_path.is_file():
        bundle_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        issuer_refs = bundle_manifest.get("corpus_bundle", {}).get("issuer_snapshots") or []
        if not issuer_refs:
            return {"macro_bindability_failures": 0, "failures": [], "skipped": True}
    try:
        _, snapshot = load_bundle_snapshot(bundle_root)
    except (FileNotFoundError, ValueError) as exc:
        if issuer_refs:
            return {
                "macro_bindability_failures": len(items),
                "failures": [
                    {
                        "item_id": item.item_id,
                        "reason": "macro_bindability",
                        "detail": str(exc),
                    }
                    for item in items
                ],
            }
        return {
            "macro_bindability_failures": 0,
            "failures": [],
            "skipped": True,
            "skip_reason": str(exc),
        }
    failures: list[dict[str, str]] = []
    for item in items:
        ok, detail = check_item_macro_bindable(item, snapshot)
        if not ok:
            failures.append(
                {
                    "item_id": item.item_id,
                    "reason": "macro_bindability",
                    "detail": detail,
                }
            )
    return {
        "macro_bindability_failures": len(failures),
        "failures": failures,
    }
