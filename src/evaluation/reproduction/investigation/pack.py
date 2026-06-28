"""Failure investigation pack export: HTML + CSV (019)."""

from __future__ import annotations

import csv
import html
from pathlib import Path

from evaluation.generation.review.annotations import latest_annotations_by_item
from evaluation.reproduction.investigation._loaders import (
    InvestigationInputs,
    load_investigation_inputs,
    outcome_and_ranking,
)
from evaluation.reproduction.investigation.edgar_links import build_edgar_links
from evaluation.reproduction.investigation.graph_context import write_graph_context_panels
from evaluation.reproduction.investigation.materialization_audit import build_materialization_audit
from evaluation.reproduction.investigation.taxonomy import (
    _judge_scores,
    _synthesis_path,
    suggest_failure_class,
)
from evaluation.reproduction.report_models import FailureInvestigationFields
from models.investigation import (
    CitationExcerpt,
    CorpusExcerpt,
    CorpusExcerptSource,
    FailureInvestigationRow,
)


def _resolve_corpus_excerpt(bundle_root: Path, section_path: str, *, max_chars: int = 400) -> CorpusExcerpt:
    rel = section_path.strip()
    if not rel:
        return CorpusExcerpt(section_path=rel, text="", source=CorpusExcerptSource.POINTER)
    parts = rel.split("/", 1)
    accession = parts[0] if parts else rel
    section_slug = parts[1] if len(parts) > 1 else ""
    corpus_root = bundle_root / "corpus"
    candidates = [
        corpus_root / "sections" / accession / f"{section_slug}.txt",
        corpus_root / "sections" / f"{rel}.txt",
    ]
    for candidate in candidates:
        if candidate.is_file():
            text = candidate.read_text(encoding="utf-8", errors="replace").strip()
            excerpt = text[:max_chars] + ("…" if len(text) > max_chars else "")
            return CorpusExcerpt(
                section_path=rel,
                text=excerpt,
                source=CorpusExcerptSource.BUNDLE_SECTION,
            )
    return CorpusExcerpt(
        section_path=rel,
        text=f"[corpus pointer] {rel}",
        source=CorpusExcerptSource.POINTER,
    )


def build_failure_investigation_rows(
    draft: Path,
    *,
    repro_input: Path | None,
    variant: str = "graph-full",
    item_ids: list[str] | None = None,
    queue_file: Path | None = None,
    inputs: InvestigationInputs | None = None,
) -> list[FailureInvestigationRow]:
    ctx = inputs or load_investigation_inputs(
        draft,
        repro_input=repro_input,
        variant=variant,
        item_ids=item_ids,
        queue_file=queue_file,
    )
    latest_ann = latest_annotations_by_item(ctx.bundle_root)
    rows: list[FailureInvestigationRow] = []

    for item_id in ctx.item_ids:
        item = ctx.items_by_id.get(item_id)
        if item is None:
            continue
        result = ctx.repro_by_id.get(item_id)
        queue_entry = ctx.queue_by_id.get(item_id)
        outcome, mrr, ndcg = outcome_and_ranking(result)
        audit = build_materialization_audit(
            bundle_root=ctx.bundle_root,
            item=item,
            result=result,
        )
        suggested, detail = suggest_failure_class(
            item=item,
            result=result,
            materialization_audit=audit,
        )
        gt = item.ground_truth
        accessions = list(item.expected_bindings.accessions) if item.expected_bindings else []
        if result and result.answer and result.answer.citations:
            for citation in result.answer.citations:
                if citation.accession and citation.accession not in accessions:
                    accessions.append(citation.accession)

        citation_excerpts = []
        if result and result.answer and result.answer.citations:
            for citation in result.answer.citations[:8]:
                citation_excerpts.append(
                    CitationExcerpt(
                        chunk_node_id=citation.chunk_node_id,
                        accession=citation.accession,
                        section_id=citation.section_id,
                        excerpt=(citation.excerpt or "")[:300],
                    )
                )

        corpus_excerpts = [
            _resolve_corpus_excerpt(ctx.bundle_root, path)
            for path in (item.expected_section_paths or [])[:5]
        ]
        ann = latest_ann.get(item_id)
        judge_rationale = ""
        judge_status = ""
        if result:
            judge_status = result.judge_status or ""
            if result.judge_verdict:
                judge_rationale = (result.judge_verdict.rationale or "")[:2000]

        row = FailureInvestigationRow(
            item_id=item_id,
            priority_tier=queue_entry.priority_tier if queue_entry else None,
            priority_score=queue_entry.priority_score if queue_entry else None,
            inspiration_profile=item.inspiration_profile,
            question=item.question,
            expected_answer=(gt.answer or "").strip(),
            required_claims=list(gt.required_claims or []),
            expected_section_paths=list(item.expected_section_paths or []),
            agent_answer=(result.answer.text if result and result.answer else "") or "",
            citation_excerpts=citation_excerpts,
            outcome_score=outcome,
            mrr=mrr,
            ndcg_at_10=ndcg,
            judge_status=judge_status,
            judge_rationale=judge_rationale,
            judge_scores=_judge_scores(result),
            synthesis_path=_synthesis_path(result),
            suggested_failure_class=suggested,
            suggested_failure_detail=detail,
            human_failure_class=ann.failure_class.value if ann else "",
            human_annotation_notes=ann.notes if ann and ann.notes else "",
            edgar_links=build_edgar_links(ctx.bundle_root, accessions),
            corpus_excerpts=corpus_excerpts,
            materialization_audit=audit,
            repro_result_path=str(ctx.repro_results_path) if ctx.repro_results_path else "",
            repro_missing=result is None,
        )
        rows.append(row)
    return rows


def row_to_csv_dict(row: FailureInvestigationRow) -> dict[str, str]:
    edgar = " | ".join(
        link.url or f"{link.accession} ({link.link_omitted_reason})" for link in row.edgar_links
    )
    corpus = " | ".join(ex.section_path + ": " + ex.text[:120] for ex in row.corpus_excerpts)
    citations = " | ".join(
        f"{c.chunk_node_id}:{c.excerpt[:80]}" for c in row.citation_excerpts
    )
    return {
        "item_id": row.item_id,
        "priority_tier": str(row.priority_tier or ""),
        "priority_score": f"{row.priority_score:.3f}" if row.priority_score is not None else "",
        "inspiration_profile": row.inspiration_profile,
        "question": row.question,
        "expected_answer": row.expected_answer,
        "agent_answer": row.agent_answer,
        "outcome_score": f"{row.outcome_score:.3f}" if row.outcome_score is not None else "",
        "mrr": f"{row.mrr:.3f}" if row.mrr is not None else "",
        "ndcg_at_10": f"{row.ndcg_at_10:.3f}" if row.ndcg_at_10 is not None else "",
        "synthesis_path": row.synthesis_path,
        "suggested_failure_class": row.suggested_failure_class.value if row.suggested_failure_class else "",
        "suggested_failure_detail": row.suggested_failure_detail,
        "human_failure_class": row.human_failure_class,
        "human_annotation_notes": row.human_annotation_notes,
        "judge_status": row.judge_status,
        "judge_rationale": row.judge_rationale[:500],
        "edgar_links": edgar,
        "corpus_excerpts": corpus,
        "binding_miss": str(row.materialization_audit.binding_miss if row.materialization_audit else False),
        "repro_missing": str(row.repro_missing),
        "citation_excerpts": citations,
        "graph_context_href": row.graph_context_href,
    }


def write_failure_investigation_csv(rows: list[FailureInvestigationRow], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(row_to_csv_dict(FailureInvestigationRow(item_id="")).keys()) if not rows else list(
        row_to_csv_dict(rows[0]).keys()
    )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row_to_csv_dict(row))
    return path


def render_failure_investigation_html(
    rows: list[FailureInvestigationRow],
    *,
    title: str = "Failure Investigation Pack",
) -> str:
    sections: list[str] = []
    for row in rows:
        edgar_bits = []
        for link in row.edgar_links:
            label = f"{link.form_type} {link.period_end or ''} — {link.accession}".strip()
            if link.url:
                edgar_bits.append(f"<a href='{html.escape(link.url)}'>{html.escape(label)}</a>")
            else:
                edgar_bits.append(
                    f"{html.escape(label)} ({html.escape(link.link_omitted_reason or 'no link')})"
                )
        corpus_bits = "<br>".join(
            f"<code>{html.escape(ex.section_path)}</code>: {html.escape(ex.text)}"
            for ex in row.corpus_excerpts
        )
        audit = row.materialization_audit
        audit_txt = ""
        if audit:
            audit_txt = (
                f"<p><strong>Materialization audit:</strong> snapshot={html.escape(audit.snapshot_id)}; "
                f"binding_miss={audit.binding_miss}; "
                f"expected={html.escape(', '.join(audit.expected_section_paths[:5]))}; "
                f"visited={html.escape(', '.join(audit.visited_section_paths[:5]))}</p>"
            )
        graph_link = ""
        if row.graph_context_href:
            graph_link = (
                f"<p><a href='{html.escape(row.graph_context_href)}'>Graph context panel</a></p>"
            )
        missing = "<p><em>Repro result missing for this item</em></p>" if row.repro_missing else ""
        sections.append(
            "<section class='investigation-item'>"
            f"<h2>{html.escape(row.item_id)} "
            f"<span class='profile'>({html.escape(row.inspiration_profile)})</span></h2>"
            f"{missing}"
            f"<p><strong>Suggested failure:</strong> "
            f"{html.escape(row.suggested_failure_class.value if row.suggested_failure_class else 'unclassified')} "
            f"— {html.escape(row.suggested_failure_detail)}</p>"
            f"<p><strong>Human annotation:</strong> {html.escape(row.human_failure_class)} "
            f"— {html.escape(row.human_annotation_notes)}</p>"
            f"<p><strong>Question:</strong> {html.escape(row.question)}</p>"
            f"<p><strong>Expected:</strong> {html.escape(row.expected_answer)}</p>"
            f"<p><strong>Agent answer:</strong></p>"
            f"<pre class='answer-block'>{html.escape(row.agent_answer)}</pre>"
            f"<p><strong>Repro:</strong> outcome={html.escape(str(row.outcome_score))} "
            f"MRR={html.escape(str(row.mrr))} nDCG={html.escape(str(row.ndcg_at_10))} "
            f"synthesis={html.escape(row.synthesis_path)}</p>"
            f"<p><strong>Judge:</strong> {html.escape(row.judge_status)}</p>"
            f"<pre class='answer-block'>{html.escape(row.judge_rationale[:1500])}</pre>"
            f"<p><strong>EDGAR links:</strong> {' · '.join(edgar_bits) or '—'}</p>"
            f"<p><strong>Corpus excerpts:</strong><br>{corpus_bits or '—'}</p>"
            f"{audit_txt}{graph_link}"
            "</section>"
        )
    body = "\n".join(sections) if sections else "<p>No items selected.</p>"
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;}"
        "pre.answer-block{white-space:pre-wrap;background:#f8f8f8;padding:0.75rem;border-radius:4px;}"
        "section.investigation-item{border-bottom:1px solid #ddd;padding-bottom:1.5rem;margin-bottom:1.5rem;}"
        ".profile{color:#666;font-size:0.9rem;}"
        "</style></head><body>"
        f"<h1>{html.escape(title)}</h1>"
        f"{body}</body></html>"
    )


def export_failure_investigation_pack(
    draft: Path,
    output_dir: Path,
    *,
    repro_input: Path | None,
    variant: str = "graph-full",
    item_ids: list[str] | None = None,
    queue_file: Path | None = None,
) -> tuple[Path, Path]:
    rows = build_failure_investigation_rows(
        draft,
        repro_input=repro_input,
        variant=variant,
        item_ids=item_ids,
        queue_file=queue_file,
    )
    inputs = load_investigation_inputs(
        draft,
        repro_input=repro_input,
        variant=variant,
        item_ids=[r.item_id for r in rows],
        queue_file=queue_file,
    )
    write_graph_context_panels(rows, output_dir, bundle_root=inputs.bundle_root)
    html_path = output_dir / "failure_investigation.html"
    csv_path = output_dir / "failure_investigation.csv"
    html_path.write_text(render_failure_investigation_html(rows), encoding="utf-8")
    write_failure_investigation_csv(rows, csv_path)
    return html_path, csv_path


def failure_investigation_fields_for_row(row: FailureInvestigationRow) -> FailureInvestigationFields:
    return FailureInvestigationFields(
        suggested_failure_class=row.suggested_failure_class.value if row.suggested_failure_class else "",
        suggested_failure_detail=row.suggested_failure_detail,
        human_failure_class=row.human_failure_class,
        synthesis_path=row.synthesis_path,
        edgar_links_html=_render_edgar_links_html(row),
        corpus_excerpts_html=_render_corpus_html(row),
        materialization_audit_html=_render_audit_html(row),
        graph_context_href=row.graph_context_href,
    )


def _render_edgar_links_html(row: FailureInvestigationRow) -> str:
    parts = []
    for link in row.edgar_links:
        label = f"{link.form_type} {link.period_end or ''} — {link.accession}".strip()
        if link.url:
            parts.append(f"<a href='{html.escape(link.url)}'>{html.escape(label)}</a>")
        else:
            parts.append(f"{html.escape(label)} ({html.escape(link.link_omitted_reason)})")
    return " · ".join(parts) if parts else "—"


def _render_corpus_html(row: FailureInvestigationRow) -> str:
    return "<br>".join(
        f"<code>{html.escape(ex.section_path)}</code>: {html.escape(ex.text)}"
        for ex in row.corpus_excerpts
    ) or "—"


def _render_audit_html(row: FailureInvestigationRow) -> str:
    audit = row.materialization_audit
    if not audit:
        return "—"
    return (
        f"snapshot={html.escape(audit.snapshot_id)}; binding_miss={audit.binding_miss}; "
        f"expected={html.escape(', '.join(audit.expected_section_paths[:5]))}; "
        f"visited={html.escape(', '.join(audit.visited_section_paths[:5]))}"
    )
