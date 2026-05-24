"""Section narrative ontology for graph materialization (009-E)."""

from __future__ import annotations

import re

from models.enums import EvidenceSourceType, NarrativeSectionKind
from models.filing import SectionBlock

_ITEM_IN_LABEL = re.compile(r"\bitem\s+(1a|1|7)\b", re.I)
_KIND_FROM_SECTION_ID = {
    "md_and_a": NarrativeSectionKind.MD_AND_A,
    "mda": NarrativeSectionKind.MD_AND_A,
    "risk_factors": NarrativeSectionKind.RISK_FACTORS,
    "business_description": NarrativeSectionKind.BUSINESS_DESCRIPTION,
}


def infer_narrative_kind(
    *,
    section_id: str,
    title: str,
    source_type: str | EvidenceSourceType = EvidenceSourceType.XBRL,
    narrative_kind: NarrativeSectionKind | None = None,
) -> str:
    if narrative_kind is not None:
        return narrative_kind.value
    sid = section_id.lower()
    if sid.startswith("html-"):
        for key, kind in _KIND_FROM_SECTION_ID.items():
            if key in sid:
                return kind.value
    if "xbrl-facts" in sid or sid.endswith("-xbrl-facts"):
        return "xbrl_bucket"
    title_lower = title.lower()
    if "risk factor" in title_lower or "item 1a" in title_lower:
        return NarrativeSectionKind.RISK_FACTORS.value
    if "management" in title_lower and "discussion" in title_lower:
        return NarrativeSectionKind.MD_AND_A.value
    if re.search(r"\bitem\s+7\b", title_lower) or "md&a" in title_lower:
        return NarrativeSectionKind.MD_AND_A.value
    if "item 1." in title_lower and "business" in title_lower:
        return NarrativeSectionKind.BUSINESS_DESCRIPTION.value
    raw = getattr(source_type, "value", str(source_type)).lower()
    if raw == EvidenceSourceType.HTML.value:
        return NarrativeSectionKind.OTHER.value
    return NarrativeSectionKind.OTHER.value


def infer_item_number(
    *,
    narrative_kind: str,
    section_id: str,
    title: str,
) -> str:
    if narrative_kind == NarrativeSectionKind.RISK_FACTORS.value:
        return "1A"
    if narrative_kind == NarrativeSectionKind.MD_AND_A.value:
        return "7"
    if narrative_kind == NarrativeSectionKind.BUSINESS_DESCRIPTION.value:
        return "1"
    match = _ITEM_IN_LABEL.search(title)
    if match:
        return (match.group(1) or "").upper()
    sid = section_id.lower()
    if "1a" in sid or "risk_factors" in sid:
        return "1A"
    if "md_and_a" in sid or "mda" in sid:
        return "7"
    return ""


def section_node_properties(sec: SectionBlock) -> dict:
    source = getattr(sec.source_type, "value", str(sec.source_type))
    kind = infer_narrative_kind(
        section_id=sec.section_id,
        title=sec.title,
        source_type=source,
        narrative_kind=sec.narrative_kind,
    )
    item = infer_item_number(
        narrative_kind=kind,
        section_id=sec.section_id,
        title=sec.title,
    )
    props = {
        "level": sec.level,
        "section_id": sec.section_id,
        "source_type": source,
        "narrative_kind": kind,
    }
    if item:
        props["item_number"] = item
    return props


def xbrl_bucket_properties() -> dict:
    return {
        "level": 0,
        "section_id": "xbrl-facts",
        "source_type": EvidenceSourceType.XBRL.value,
        "narrative_kind": "xbrl_bucket",
        "xbrl": True,
    }
