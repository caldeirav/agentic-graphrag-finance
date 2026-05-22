"""Parse XBRL packages from live SEC download cache."""

from __future__ import annotations

from pathlib import Path

from models.filing import FilingRef
from models.ingestion import CacheEntry, XBRLArtifactManifest
from models.parsing import ParsedDocument
from parsing.docling_pipeline import find_primary_parse_path, parse_filing_path


def load_manifest(entry: CacheEntry) -> XBRLArtifactManifest:
    return XBRLArtifactManifest.model_validate_json(entry.manifest_path.read_text())


def filing_ref_from_manifest(manifest: XBRLArtifactManifest) -> FilingRef:
    r = manifest.resolution
    return FilingRef(
        cik=r.cik,
        accession=r.accession,
        form_type=r.form_type,
        filed_at=r.filed_at,
        period_end=r.period_end,
        source_uri=r.edgar_filing_url or f"edgar://{r.accession}",
    )


def parse_from_cache(
    entry: CacheEntry,
    *,
    skip_html_narrative: bool = False,
) -> ParsedDocument:
    manifest = load_manifest(entry)
    instance = find_primary_parse_path(entry.local_path, manifest)
    filing = filing_ref_from_manifest(manifest)
    doc = parse_filing_path(instance, filing, package_root=entry.local_path)
    from parsing.html_narrative import enrich_document_with_html_narrative

    return enrich_document_with_html_narrative(
        doc,
        entry.local_path,
        manifest,
        skip=skip_html_narrative,
    )


def write_parsed_document(
    doc: ParsedDocument,
    parsed_root: Path,
    *,
    ticker: str | None = None,
) -> Path:
    issuer = (ticker or doc.filing.cik).upper() if ticker else doc.filing.cik
    out_dir = parsed_root / issuer.upper()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{doc.filing.accession}.json"
    out_path.write_text(doc.model_dump_json(indent=2))
    return out_path
