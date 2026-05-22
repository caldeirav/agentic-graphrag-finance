"""Extract MD&A, risk factors, and business description from filing HTML."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import yaml
from bs4 import BeautifulSoup

from ingestion.html_narrative import resolve_narrative_html
from models.enums import EvidenceSourceType, HtmlNarrativeStatus, NarrativeSectionKind
from models.filing import SectionBlock
from models.ingestion import XBRLArtifactManifest
from models.parsing import ParsedDocument

_SECTION_KIND_ORDER = (
    NarrativeSectionKind.BUSINESS_DESCRIPTION,
    NarrativeSectionKind.RISK_FACTORS,
    NarrativeSectionKind.MD_AND_A,
)


def load_section_patterns(config_path: Path | None = None) -> dict[str, list[str]]:
    path = config_path or Path("configs/html_narrative.yaml")
    if not path.exists():
        return {
            "business_description": ["item 1", "business"],
            "risk_factors": ["item 1a", "risk factors"],
            "md_and_a": ["item 7", "management's discussion", "md&a"],
        }
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("section_patterns", {})


def _is_xml_narrative_path(path: Path) -> bool:
    name = path.name.lower()
    return path.suffix.lower() == ".xml" or name.endswith("_htm.xml") or name.endswith("_ins.xml")


def _parse_narrative_soup(path: Path, raw: str) -> BeautifulSoup:
    """Parse inline XBRL/XML or HTML filing documents without HTML-on-XML warnings."""
    if _is_xml_narrative_path(path):
        return BeautifulSoup(raw, "lxml-xml")
    return BeautifulSoup(raw, "lxml")


def _classify_heading(text: str, patterns: dict[str, list[str]]) -> NarrativeSectionKind:
    lower = re.sub(r"\s+", " ", text.lower()).strip()
    for kind in _SECTION_KIND_ORDER:
        key = kind.value
        for pat in patterns.get(key, []):
            if pat in lower:
                return kind
    return NarrativeSectionKind.OTHER


_ITEM_HEADING = re.compile(
    r"(?is)\bitem\s+(1a|1|7)\b[\s\.\-–—:]*"
    r"(risk\s+factors|business|management.?s\s+discussion|md&a)?"
)


def _extract_sections_from_item_boundaries(
    text: str,
    patterns: dict[str, list[str]],
) -> list[SectionBlock]:
    """Split inline iXBRL / filing text on SEC Item headings (full document)."""
    matches = list(_ITEM_HEADING.finditer(text))
    if len(matches) < 2:
        return []

    sections: list[SectionBlock] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if len(chunk) < 200:
            continue
        chunk = BeautifulSoup(chunk, "lxml").get_text("\n", strip=True)
        if len(chunk) < 500:
            continue
        if chunk.count("Item ") > 8 and len(chunk) < 3000:
            continue
        title = re.sub(r"\s+", " ", match.group(0))[:200]
        kind = _classify_heading(title, patterns)
        if kind == NarrativeSectionKind.OTHER:
            item_num = (match.group(1) or "").lower()
            if item_num == "1a":
                kind = NarrativeSectionKind.RISK_FACTORS
            elif item_num == "7":
                kind = NarrativeSectionKind.MD_AND_A
            elif item_num == "1":
                kind = NarrativeSectionKind.BUSINESS_DESCRIPTION
        sections.append(
            SectionBlock(
                section_id=f"html-{kind.value}-{idx}",
                title=title,
                level=1,
                text=chunk[:80000],
                source_type=EvidenceSourceType.HTML,
                narrative_kind=kind,
            )
        )
    return sections


def extract_narrative_sections(
    html_path: Path,
    *,
    form_type: str = "10-K",
) -> list[SectionBlock]:
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    patterns = load_section_patterns()

    by_item = _extract_sections_from_item_boundaries(raw, patterns)
    if by_item:
        return by_item

    soup = _parse_narrative_soup(html_path, raw)

    headings: list[tuple[str, NarrativeSectionKind, object]] = []
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "p", "div", "span", "b", "strong"]):
        text = tag.get_text(" ", strip=True)
        if not text or len(text) > 200:
            continue
        kind = _classify_heading(text, patterns)
        if kind != NarrativeSectionKind.OTHER or re.search(r"item\s+\d", text, re.I):
            headings.append((text, kind, tag))

    if not headings:
        body = soup.get_text("\n", strip=True)
        if len(body) > 500:
            risk_match = re.search(
                r"(?is)(\bitem\s+1a\b.{0,80}?\brisk\s+factors\b)(.+?)(?=\bitem\s+\d|\Z)",
                body,
            )
            if risk_match:
                return [
                    SectionBlock(
                        section_id="html-risk_factors-0",
                        title="Item 1A Risk Factors",
                        level=1,
                        text=risk_match.group(0)[:80000],
                        source_type=EvidenceSourceType.HTML,
                        narrative_kind=NarrativeSectionKind.RISK_FACTORS,
                    )
                ]
            return [
                SectionBlock(
                    section_id="html-narrative-generic",
                    title="Narrative (generic)",
                    level=1,
                    text=body[:80000],
                    source_type=EvidenceSourceType.HTML,
                    narrative_kind=NarrativeSectionKind.OTHER,
                )
            ]
        return []

    sections: list[SectionBlock] = []
    for idx, (title, kind, tag) in enumerate(headings):
        parts: list[str] = []
        for sib in tag.find_all_next(string=True):
            parts.append(str(sib).strip())
            if len(" ".join(parts)) > 8000:
                break
        body = " ".join(p for p in parts if p)[:50000]
        if len(body) < 80:
            continue
        sid = f"html-{kind.value}-{idx}"
        sections.append(
            SectionBlock(
                section_id=sid,
                title=title[:200],
                level=1,
                text=body,
                source_type=EvidenceSourceType.HTML,
                narrative_kind=kind,
            )
        )
    return sections


def _recompute_content_hash(doc: ParsedDocument) -> str:
    payload = doc.model_dump_json()
    return hashlib.sha256(payload.encode()).hexdigest()


def merge_html_into_document(
    doc: ParsedDocument,
    html_sections: list[SectionBlock],
    *,
    html_artifact_path: str,
    status: HtmlNarrativeStatus,
) -> ParsedDocument:
    merged_sections = list(doc.sections) + list(html_sections)
    return doc.model_copy(
        update={
            "sections": merged_sections,
            "html_narrative_status": status,
            "html_artifact_path": html_artifact_path,
            "content_hash": _recompute_content_hash(
                doc.model_copy(update={"sections": merged_sections})
            ),
        }
    )


def enrich_document_with_html_narrative(
    doc: ParsedDocument,
    package_root: Path,
    manifest: XBRLArtifactManifest,
    *,
    skip: bool = False,
) -> ParsedDocument:
    if skip:
        return doc.model_copy(update={"html_narrative_status": HtmlNarrativeStatus.SKIPPED})
    resolved = resolve_narrative_html(package_root, manifest)
    if resolved is None:
        return doc.model_copy(update={"html_narrative_status": HtmlNarrativeStatus.FAILED})
    try:
        sections = extract_narrative_sections(resolved.path, form_type=doc.filing.form_type)
    except Exception:
        return doc.model_copy(update={"html_narrative_status": HtmlNarrativeStatus.FAILED})
    if not sections:
        return doc.model_copy(
            update={
                "html_narrative_status": HtmlNarrativeStatus.FAILED,
                "html_artifact_path": str(resolved.path.relative_to(package_root)),
            }
        )
    rel = str(resolved.path.relative_to(package_root))
    return merge_html_into_document(
        doc,
        sections,
        html_artifact_path=rel,
        status=HtmlNarrativeStatus.SUCCESS,
    )
