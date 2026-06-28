"""Link-first offline graph context panels for cited evidence nodes (019)."""

from __future__ import annotations

import html
import json
from pathlib import Path

from models.investigation import FailureInvestigationRow


def _pre_rendered_context(bundle_root: Path, item_id: str) -> dict | None:
    path = bundle_root / "corpus" / "graph_context" / f"{item_id}.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def render_graph_context_panel(row: FailureInvestigationRow) -> str:
    cited = row.citation_excerpts[:8]
    nodes_html = "".join(
        f"<li><code>{html.escape(c.chunk_node_id)}</code> "
        f"({html.escape(c.accession)}/{html.escape(c.section_id)})</li>"
        for c in cited
    )
    audit = row.materialization_audit
    audit_html = ""
    if audit:
        audit_html = (
            f"<p>Snapshot: {html.escape(audit.snapshot_id)}</p>"
            f"<p>Visited sections: {html.escape(', '.join(audit.visited_section_paths[:10]))}</p>"
        )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<title>Graph context — {html.escape(row.item_id)}</title>"
        "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;}"
        "code{background:#f4f4f4;padding:0.1rem 0.3rem;border-radius:3px;}</style></head><body>"
        f"<h1>{html.escape(row.item_id)}</h1>"
        f"<p><strong>Question:</strong> {html.escape(row.question)}</p>"
        f"{audit_html}"
        f"<h2>Cited nodes</h2><ul>{nodes_html or '<li><em>No cited nodes</em></li>'}</ul>"
        "</body></html>"
    )


def write_graph_context_panels(
    rows: list[FailureInvestigationRow],
    output_dir: Path,
    *,
    bundle_root: Path,
) -> None:
    panel_dir = output_dir / "graph_context"
    panel_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        pre = _pre_rendered_context(bundle_root, row.item_id)
        row.graph_context_href = f"graph_context/{row.item_id}.html"
        row.graph_context_inline = pre is not None
        panel_path = panel_dir / f"{row.item_id}.html"
        if pre and pre.get("html"):
            panel_path.write_text(str(pre["html"]), encoding="utf-8")
        else:
            panel_path.write_text(render_graph_context_panel(row), encoding="utf-8")
