"""Docling XBRL conversion (InputFormat.XML_XBRL).

Follows: https://docling-project.github.io/docling/examples/xbrl_conversion/
Requires: ``docling[xbrl]`` (arelle-release).
"""

from __future__ import annotations

import hashlib
import logging
import textwrap
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from models.filing import FilingRef, SectionBlock, TableBlock
from models.parsing import ParsedDocument
from parsing.errors import ParseError

PARSER_VERSION = "docling-xbrl-1.0.0"


def load_docling_config(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/docling_xbrl.yaml")
    if not path.exists():
        return {"parse_confidence_threshold": 0.5, "xbrl": {"enable_remote_fetch": True}}
    return yaml.safe_load(path.read_text()) or {}

if TYPE_CHECKING:
    from docling.document_converter import DocumentConverter
    from docling_core.types.doc.document import DoclingDocument

logger = logging.getLogger(__name__)


def is_xbrl_instance_path(path: Path) -> bool:
    """True when path is an XBRL instance document (not a linkbase-only file)."""
    if path.suffix.lower() != ".xml":
        return False
    name = path.name.lower()
    if name.endswith("_htm.xml") or name.endswith("_ins.xml"):
        return True
    if any(name.endswith(s) for s in ("_cal.xml", "_def.xml", "_lab.xml", "_pre.xml")):
        return False
    try:
        head = path.read_bytes()[:4096].lower()
    except OSError:
        return False
    return b"xbrl" in head or b"http://www.xbrl.org" in head


def _instance_taxonomy_stem(instance_path: Path) -> str:
    """e.g. ``aapl-20250927_htm.xml`` → ``aapl-20250927``."""
    stem = instance_path.stem
    for suffix in ("_htm", "_ins"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def _dir_has_taxonomy_zip(directory: Path) -> bool:
    return any(
        p.is_file() and p.suffix.lower() == ".zip" and "xbrl" in p.name.lower()
        for p in directory.iterdir()
    )


def find_taxonomy_dir(package_root: Path, instance_path: Path) -> Path:
    """Directory of XSD + linkbases only (no ``*-xbrl.zip`` — Docling passes zips to Arelle)."""
    stem = _instance_taxonomy_stem(instance_path)
    xbrl_extracted = package_root / "xbrl_extracted"
    if xbrl_extracted.is_dir() and list(xbrl_extracted.glob("*.xsd")):
        return xbrl_extracted

    taxonomy_sub = package_root / "taxonomy"
    if taxonomy_sub.is_dir() and list(taxonomy_sub.glob("*.xsd")):
        return taxonomy_sub

    candidates: list[Path] = []
    for directory in (instance_path.parent, package_root):
        if directory.is_dir() and list(directory.glob("*.xsd")) and directory not in candidates:
            candidates.append(directory)

    scored: list[tuple[int, Path]] = []
    for directory in candidates:
        if _dir_has_taxonomy_zip(directory):
            continue
        xsds = list(directory.glob("*.xsd"))
        if not xsds:
            continue
        linkbases = sum(
            1
            for p in directory.iterdir()
            if p.suffix.lower() == ".xml"
            and "_htm" not in p.name.lower()
            and not p.name.lower().endswith("_htm.xml")
        )
        stem_match = 50 if any(stem in p.stem for p in xsds) else 0
        scored.append((stem_match + len(xsds) * 10 + linkbases, directory))

    if scored:
        scored.sort(key=lambda x: (-x[0], len(str(x[1]))))
        return scored[0][1]
    return instance_path.parent


def _format_xbrl_dimension_label(dim_qname: object, dim_value: object) -> str:
    """Safe dimension label for Docling 2.94.0 (null memberQname on typed dimensions)."""
    member = getattr(dim_value, "memberQname", None)
    local = getattr(member, "localName", None) if member is not None else None
    dim_local = getattr(dim_qname, "localName", str(dim_qname))
    if local:
        return f"{dim_local}: {local}"
    return f"{dim_local}: (unspecified)"


def _apply_docling_xbrl_dimension_patch() -> None:
    """Patch Docling XBRL backend convert() for SEC filings with typed dimensions."""
    import inspect

    import docling.backend.xml.xbrl_backend as mod

    if getattr(mod, "_agf_patch_applied", False):
        return

    broken = 'f"{dim_qname.localName}: {dim_value.memberQname.localName}"'
    fixed = "_format_xbrl_dimension_label(dim_qname, dim_value)"
    try:
        src = inspect.getsource(mod.XBRLDocumentBackend.convert)
    except (OSError, TypeError):
        logger.warning("Could not read Docling XBRL convert source for dimension patch")
        mod._agf_patch_applied = True
        return

    if broken not in src:
        logger.warning("Docling XBRL convert source changed; dimension patch not applied")
        mod._agf_patch_applied = True
        return

    src = textwrap.dedent(src.replace(broken, fixed))
    src = "\n".join(line for line in src.splitlines() if line.strip() != "@override")
    namespace = {name: getattr(mod, name) for name in dir(mod) if not name.startswith("__")}
    namespace["_format_xbrl_dimension_label"] = _format_xbrl_dimension_label
    exec(compile(src, "<patched_xbrl_convert>", "exec"), namespace)  # noqa: S102
    mod.XBRLDocumentBackend.convert = namespace["convert"]  # type: ignore[method-assign]
    mod._agf_patch_applied = True


def build_xbrl_converter(
    taxonomy_dir: Path,
    *,
    enable_remote_fetch: bool,
) -> DocumentConverter:
    from docling.datamodel.backend_options import XBRLBackendOptions
    from docling.datamodel.base_models import InputFormat
    from docling.document_converter import DocumentConverter, XBRLFormatOption

    backend_options = XBRLBackendOptions(
        enable_local_fetch=True,
        enable_remote_fetch=enable_remote_fetch,
        taxonomy=taxonomy_dir,
    )
    return DocumentConverter(
        allowed_formats=[InputFormat.XML_XBRL],
        format_options={
            InputFormat.XML_XBRL: XBRLFormatOption(backend_options=backend_options)
        },
    )


def _content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _table_from_docling_item(
    table_item: object, table_id: str, doc: DoclingDocument
) -> TableBlock | None:
    try:
        df = table_item.export_to_dataframe(doc=doc)  # type: ignore[attr-defined]
    except TypeError:
        try:
            df = table_item.export_to_dataframe()  # type: ignore[attr-defined]
        except Exception:
            return None
    except Exception:
        return None
    if df is None or df.empty:
        return None
    headers = [list(df.columns.astype(str))]
    rows = [[str(v) for v in row] for row in df.values.tolist()]
    return TableBlock(table_id=table_id, headers=headers, rows=rows)


def _tables_from_key_value(doc: DoclingDocument) -> list[TableBlock]:
    tables: list[TableBlock] = []
    for ki, kv_item in enumerate(getattr(doc, "key_value_items", []) or []):
        graph = getattr(kv_item, "graph", None)
        if graph is None:
            continue
        rows: list[list[str]] = []
        for link in graph.links:
            source = next(
                (c for c in graph.cells if c.cell_id == link.source_cell_id),
                None,
            )
            target = next(
                (c for c in graph.cells if c.cell_id == link.target_cell_id),
                None,
            )
            if source is None or target is None:
                continue
            rows.append([str(source.text or ""), str(target.text or "")])
        if rows:
            tables.append(
                TableBlock(
                    table_id=f"xbrl-facts-{ki}",
                    headers=[["Concept", "Value"]],
                    rows=rows,
                )
            )
    return tables


def docling_document_to_parsed(
    doc: DoclingDocument,
    filing: FilingRef,
    *,
    content_hash: str,
) -> ParsedDocument:
    from docling_core.types.doc import DocItemLabel

    sections: list[SectionBlock] = []
    tables: list[TableBlock] = list(_tables_from_key_value(doc))
    skip_docling_tables = sum(len(t.rows) for t in tables if t.table_id.startswith("xbrl-facts")) > 50
    sec_idx = 0
    table_idx = 0

    for item, _ in doc.iterate_items():
        label = item.label
        text = (getattr(item, "text", None) or "").strip()

        if label == DocItemLabel.TITLE and text:
            sections.append(
                SectionBlock(
                    section_id=f"sec-{sec_idx}",
                    title=text[:500],
                    level=1,
                    text=text[:8000],
                )
            )
            sec_idx += 1
        elif label == DocItemLabel.TEXT and text:
            if sections and sections[-1].level >= 2:
                prev = sections[-1]
                merged = f"{prev.text}\n\n{text}".strip()[:8000]
                sections[-1] = prev.model_copy(update={"text": merged})
            elif sections:
                prev = sections[-1]
                merged = f"{prev.text}\n\n{text}".strip()[:8000]
                sections[-1] = prev.model_copy(update={"text": merged})
            else:
                sections.append(
                    SectionBlock(
                        section_id=f"sec-{sec_idx}",
                        title="Narrative",
                        level=2,
                        text=text[:8000],
                    )
                )
                sec_idx += 1
        elif label == DocItemLabel.TABLE and not skip_docling_tables:
            block = _table_from_docling_item(item, f"table-{table_idx}", doc)
            if block is not None:
                tables.append(block)
                table_idx += 1

    fact_rows = sum(len(t.rows) for t in tables if t.table_id.startswith("xbrl-facts-"))
    item_count = len(list(doc.iterate_items()))
    if fact_rows > 50 or len(tables) > 2:
        confidence = 0.95
    elif sections or tables:
        confidence = 0.88
    elif item_count > 0:
        confidence = 0.65
    else:
        confidence = 0.4

    if not sections:
        name = getattr(doc, "name", None) or filing.accession
        sections.append(
            SectionBlock(section_id="sec-0", title=str(name), level=0, text=str(name))
        )

    return ParsedDocument(
        filing=filing,
        sections=sections,
        tables=tables,
        footnotes=[],
        parse_confidence=confidence,
        parser_version=PARSER_VERSION,
        content_hash=content_hash,
    )


def parse_xbrl_instance(
    instance_path: Path,
    package_root: Path,
    filing: FilingRef,
    *,
    config_path: Path | None = None,
) -> ParsedDocument | None:
    """Convert an XBRL instance via Docling; returns None if conversion yields no usable content."""
    cfg = load_docling_config(config_path)
    xbrl_cfg = cfg.get("xbrl") or {}
    enable_remote = bool(xbrl_cfg.get("enable_remote_fetch", True))

    raw = instance_path.read_bytes()
    content_hash = _content_hash(raw)
    taxonomy_dir = find_taxonomy_dir(package_root, instance_path)
    _apply_docling_xbrl_dimension_patch()

    try:
        converter = build_xbrl_converter(taxonomy_dir, enable_remote_fetch=enable_remote)
        result = converter.convert(str(instance_path))
        parsed = docling_document_to_parsed(
            result.document,
            filing,
            content_hash=content_hash,
        )
    except Exception as exc:
        raise ParseError(f"Docling XBRL conversion failed for {instance_path}: {exc}") from exc

    threshold = float(cfg.get("parse_confidence_threshold", 0.5))
    has_facts = any(t.table_id.startswith("xbrl-facts-") for t in parsed.tables)
    has_structure = len(parsed.sections) > 1 or len(parsed.tables) > 0 or has_facts
    if parsed.parse_confidence < threshold and not has_structure:
        raise ParseError(
            f"Docling XBRL low confidence ({parsed.parse_confidence:.2f}) for {instance_path}"
        )
    return parsed
