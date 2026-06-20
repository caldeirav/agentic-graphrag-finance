"""Static HTML + CSV review pack export (018)."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from evaluation.generation.bundle import load_dev_split_items
from evaluation.generation.review._paths import resolve_draft_bundle
from evaluation.generation.review.annotations import latest_annotations_by_item
from evaluation.generation.review.queue import _load_repro_results, _outcome_score, _ranking_values
from models.benchmark_generation import GeneratedBenchmarkItem


def _resolve_corpus_excerpt(bundle_root: Path, section_path: str, *, max_chars: int = 400) -> str:
    """Return corpus pointer text for a section path (structural spot-check)."""
    rel = section_path.strip()
    if not rel:
        return ""
    parts = rel.split("/", 1)
    accession = parts[0] if parts else rel
    section_slug = parts[1] if len(parts) > 1 else ""
    corpus_root = bundle_root / "corpus"
    candidates = [
        corpus_root / "sections" / accession / f"{section_slug}.txt",
        corpus_root / "sections" / f"{rel}.txt",
        corpus_root / "graphs" / f"{accession}.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
            return text[:max_chars] + ("…" if len(text) > max_chars else "")
    return f"[corpus pointer] {rel}"


def build_review_pack_rows(
    bundle_root: Path,
    item_ids: list[str],
    *,
    repro_input: Path | None = None,
    variant: str = "graph-full",
) -> list[dict[str, str]]:
    root = resolve_draft_bundle(bundle_root)
    items = {item.item_id: item for item in load_dev_split_items(root / "items" / "dev.jsonl")}
    repro_by_id = _load_repro_results(repro_input, variant) if repro_input else {}
    latest_ann = latest_annotations_by_item(root)

    rows: list[dict[str, str]] = []
    for item_id in item_ids:
        item = items.get(item_id)
        if item is None:
            continue
        row = _item_row(item, root, repro_by_id.get(item_id), latest_ann.get(item_id))
        rows.append(row)
    return rows


def _item_row(
    item: GeneratedBenchmarkItem,
    bundle_root: Path,
    repro_row,
    annotation,
) -> dict[str, str]:
    gt = item.ground_truth
    claims = "; ".join(gt.required_claims or [])
    sections = item.expected_section_paths or []
    excerpts = " | ".join(_resolve_corpus_excerpt(bundle_root, path) for path in sections[:3])
    mrr = ndcg = outcome = ""
    if repro_row is not None:
        mrr_val, ndcg_val = _ranking_values(repro_row)
        if mrr_val is not None:
            mrr = f"{mrr_val:.3f}"
        if ndcg_val is not None:
            ndcg = f"{ndcg_val:.3f}"
        outcome = f"{_outcome_score(repro_row):.3f}"
    failure_class = ""
    notes = ""
    if annotation is not None:
        failure_class = annotation.failure_class.value
        notes = annotation.notes or ""
    return {
        "item_id": item.item_id,
        "inspiration_profile": item.inspiration_profile,
        "question": item.question,
        "canonical_answer": (gt.answer or "").strip(),
        "required_claims": claims,
        "section_paths": "; ".join(sections),
        "corpus_excerpts": excerpts,
        "mrr": mrr,
        "ndcg_at_10": ndcg,
        "outcome_score": outcome,
        "failure_class": failure_class,
        "reviewer_notes": notes,
    }


def write_review_pack_csv(rows: list[dict[str, str]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        fieldnames = [
            "item_id",
            "inspiration_profile",
            "question",
            "canonical_answer",
            "required_claims",
            "section_paths",
            "corpus_excerpts",
            "mrr",
            "ndcg_at_10",
            "outcome_score",
            "failure_class",
            "reviewer_notes",
        ]
    else:
        fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return path


def render_review_pack_html(rows: list[dict[str, str]], *, title: str = "Dataset Review Pack") -> str:
    """Render self-contained HTML using reproduction-report panel styling."""
    sections: list[str] = []
    for row in rows:
        sections.append(
            "<section class='review-item'>"
            f"<h2>{html.escape(row['item_id'])} "
            f"<span class='profile'>({html.escape(row['inspiration_profile'])})</span></h2>"
            f"<p><strong>Question:</strong> {html.escape(row['question'])}</p>"
            f"<p><strong>Canonical answer:</strong> {html.escape(row['canonical_answer'])}</p>"
            f"<p><strong>Required claims:</strong> {html.escape(row['required_claims'])}</p>"
            f"<p><strong>Section paths:</strong> {html.escape(row['section_paths'])}</p>"
            f"<p><strong>Corpus excerpts:</strong> {html.escape(row['corpus_excerpts'])}</p>"
            f"<p><strong>Repro:</strong> MRR={html.escape(row['mrr'])} "
            f"nDCG@10={html.escape(row['ndcg_at_10'])} "
            f"outcome={html.escape(row['outcome_score'])}</p>"
            f"<p><strong>Annotation:</strong> {html.escape(row['failure_class'])} — "
            f"{html.escape(row['reviewer_notes'])}</p>"
            "</section>"
        )
    body = "\n".join(sections) if sections else "<p>No items selected.</p>"
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;}"
        ".review-item{border:1px solid #ddd;border-radius:8px;padding:1rem;margin-bottom:1.5rem;}"
        ".profile{color:#666;font-size:0.9rem;}"
        "h1{border-bottom:2px solid #333;padding-bottom:0.5rem;}"
        "</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"<p>{len(rows)} item(s)</p>"
        f"{body}</body></html>"
    )


def write_review_pack(
    bundle_root: Path,
    item_ids: list[str],
    output_dir: Path,
    *,
    repro_input: Path | None = None,
    variant: str = "graph-full",
) -> tuple[Path, Path]:
    rows = build_review_pack_rows(
        bundle_root,
        item_ids,
        repro_input=repro_input,
        variant=variant,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = write_review_pack_csv(rows, output_dir / "review_pack.csv")
    html_path = output_dir / "review_pack.html"
    html_path.write_text(render_review_pack_html(rows), encoding="utf-8")
    return html_path, csv_path
