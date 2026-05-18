"""Docling-based parsing with HTML fallback for tests and offline use."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml

from models.filing import (
    FilingRef,
    FootnoteBlock,
    SectionBlock,
    TableBlock,
)
from models.ingestion import XBRLArtifactManifest, XBRLArtifactRole
from models.parsing import ParsedDocument

PARSER_VERSION = "docling-xbrl-0.1.0"


def find_primary_instance_path(root: Path, manifest: XBRLArtifactManifest) -> Path:
    """Locate primary XBRL instance XML from manifest roles."""
    for art in manifest.artifacts:
        if art.role == XBRLArtifactRole.INSTANCE:
            path = root / art.filename
            if path.exists():
                return path
    for path in sorted(root.glob("*.xml")):
        if path.is_file():
            return path
    raise FileNotFoundError(f"No instance XML under {root}")


def load_docling_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/docling_xbrl.yaml")
    if not path.exists():
        return {"parse_confidence_threshold": 0.5}
    return yaml.safe_load(path.read_text()) or {}


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_html_fallback(html: str, filing: FilingRef) -> ParsedDocument:
    """Structure-preserving lightweight HTML parse when Docling is skipped."""
    sections: list[SectionBlock] = []
    tables: list[TableBlock] = []
    footnotes: list[FootnoteBlock] = []

    for i, m in enumerate(re.finditer(r"<h[1-3][^>]*>(.*?)</h[1-3]>", html, re.I | re.S)):
        title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if title:
            sections.append(
                SectionBlock(section_id=f"sec-{i}", title=title, level=1, text=title)
            )

    table_pattern = re.compile(r"<table[^>]*>(.*?)</table>", re.I | re.S)
    for ti, tm in enumerate(table_pattern.finditer(html)):
        rows_raw = re.findall(r"<tr[^>]*>(.*?)</tr>", tm.group(1), re.I | re.S)
        rows: list[list[str]] = []
        for row in rows_raw:
            cells = re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, re.I | re.S)
            rows.append([re.sub(r"<[^>]+>", "", c).strip() for c in cells])
        if rows:
            headers = [rows[0]] if rows else [[]]
            body = rows[1:] if len(rows) > 1 else []
            tables.append(
                TableBlock(
                    table_id=f"table-{ti}",
                    headers=headers,
                    rows=body,
                )
            )

    fn_pattern = re.compile(r'<div[^>]*class="[^"]*footnote[^"]*"[^>]*>(.*?)</motion>', re.I | re.S)
    for fi, fm in enumerate(fn_pattern.finditer(html)):
        text = re.sub(r"<[^>]+>", "", fm.group(1)).strip()
        if text:
            footnotes.append(FootnoteBlock(footnote_id=f"fn-{fi}", text=text))

    if not sections:
        sections.append(
            SectionBlock(section_id="sec-0", title="Document", level=0, text="Full document")
        )

    confidence = 0.85 if tables else 0.6
    raw = html.encode("utf-8")
    return ParsedDocument(
        filing=filing,
        sections=sections,
        tables=tables,
        footnotes=footnotes,
        parse_confidence=confidence,
        parser_version=PARSER_VERSION,
        content_hash=_content_hash(raw),
    )


def parse_filing_path(
    path: Path,
    filing: FilingRef,
    *,
    config_path: Path | None = None,
    use_docling: bool = True,
) -> ParsedDocument:
    """Parse a filing file into ParsedDocument."""
    _ = load_docling_config(config_path)
    raw = path.read_bytes()
    content_hash = _content_hash(raw)

    if use_docling and path.suffix.lower() in {".pdf", ".html", ".htm", ".xhtml", ".xml"}:
        try:
            from docling.document_converter import DocumentConverter

            converter = DocumentConverter()
            result = converter.convert(str(path))
            doc = result.document
            sections = [
                SectionBlock(
                    section_id=f"sec-{i}",
                    title=getattr(item, "text", str(item))[:200],
                    level=1,
                    text=str(item)[:2000],
                )
                for i, item in enumerate(getattr(doc, "texts", [])[:50])
            ]
            tables: list[TableBlock] = []
            for ti, table in enumerate(getattr(doc, "tables", [])[:20]):
                rows = []
                if hasattr(table, "data") and table.data is not None:
                    for row in table.data:
                        rows.append([str(c) for c in row])
                if rows:
                    tables.append(
                        TableBlock(
                            table_id=f"table-{ti}",
                            headers=[rows[0]] if rows else [[]],
                            rows=rows[1:] if len(rows) > 1 else [],
                        )
                    )
            if sections or tables:
                return ParsedDocument(
                    filing=filing,
                    sections=sections or [
                        SectionBlock(section_id="sec-0", title="Document", level=0, text="")
                    ],
                    tables=tables,
                    footnotes=[],
                    parse_confidence=0.9,
                    parser_version=PARSER_VERSION,
                    content_hash=content_hash,
                )
        except Exception:
            pass

    html = raw.decode("utf-8", errors="replace")
    doc = _parse_html_fallback(html, filing)
    return doc.model_copy(update={"content_hash": content_hash})
