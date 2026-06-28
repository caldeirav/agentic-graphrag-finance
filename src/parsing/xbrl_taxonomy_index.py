"""Build XBRL taxonomy metadata from filing linkbases (labels, presentation, calculation)."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from pydantic import BaseModel, Field

LINK_NS = "http://www.xbrl.org/2003/linkbase"
XLINK_NS = "http://www.w3.org/1999/xlink"

LABEL_ROLE_STANDARD = "http://www.xbrl.org/2003/role/label"
LABEL_ROLE_TERSE = "http://www.xbrl.org/2003/role/terseLabel"
LABEL_ROLE_DOCUMENTATION = "http://www.w3.org/2003/role/documentation"
CALC_ARCROLE = "http://www.xbrl.org/2003/arcrole/summation-item"

INCOME_STATEMENT = "income_statement"
BALANCE_SHEET = "balance_sheet"
CASH_FLOW = "cash_flow"
OTHER = "other"


class XbrlConceptMeta(BaseModel):
    """Taxonomy metadata for one XBRL concept local name."""

    concept: str
    standard_label: str = ""
    terse_label: str = ""
    documentation: str = ""
    statement_role: str = OTHER
    presentation_roles: list[str] = Field(default_factory=list)
    calc_parents: list[str] = Field(default_factory=list)
    calc_children: list[str] = Field(default_factory=list)
    metric_roles: list[str] = Field(default_factory=list)


def concept_local_name(href: str) -> str:
    """Extract concept local name from an XSD fragment href."""
    fragment = href.split("#")[-1] if "#" in href else href.rsplit("/", 1)[-1]
    if "_" in fragment:
        return fragment.split("_", 1)[-1]
    return fragment


def _xlink_attr(element: ET.Element, name: str) -> str:
    return element.get(f"{{{XLINK_NS}}}{name}") or element.get(name) or ""


def _infer_statement_role(role_uri: str) -> str:
    low = role_uri.lower()
    if any(token in low for token in ("incomestatement", "statementofincome", "statementofoperations")):
        return INCOME_STATEMENT
    if any(token in low for token in ("balancesheet", "financialposition", "statementoffinancialposition")):
        return BALANCE_SHEET
    if any(token in low for token in ("cashflow", "statementofcashflows")):
        return CASH_FLOW
    return OTHER


def _infer_roles_from_label_text(label: str) -> list[str]:
    merged: list[str] = []
    low = label.lower()
    if "net income" in low or "net earnings" in low or "net profit" in low:
        merged.extend(["net_income", "margin_numerator"])
    if "before income tax" in low or "pretax" in low or "pre-tax" in low:
        merged.append("pretax_income")
    if re.search(r"\brevenues?\b", low) or "total revenue" in low:
        merged.extend(["revenue", "total_revenue", "margin_denominator"])
    deduped: list[str] = []
    for role in merged:
        if role not in deduped:
            deduped.append(role)
    return deduped


def _parse_label_linkbase(path: Path, index: dict[str, XbrlConceptMeta]) -> None:
    root = ET.parse(path).getroot()
    locators: dict[str, str] = {}
    labels: dict[str, tuple[str, str]] = {}

    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag == "loc":
            label_id = _xlink_attr(element, "label")
            href = _xlink_attr(element, "href")
            if label_id and href:
                locators[label_id] = concept_local_name(href)
        elif tag == "label":
            label_id = _xlink_attr(element, "label")
            role = _xlink_attr(element, "role") or LABEL_ROLE_STANDARD
            text = (element.text or "").strip()
            if label_id and text:
                labels[label_id] = (role, text)
        elif tag == "labelArc":
            src = _xlink_attr(element, "from")
            dst = _xlink_attr(element, "to")
            concept = locators.get(src)
            label_info = labels.get(dst)
            if not concept or not label_info:
                continue
            role, text = label_info
            meta = index.setdefault(concept, XbrlConceptMeta(concept=concept))
            if role == LABEL_ROLE_STANDARD and not meta.standard_label:
                meta.standard_label = text
            elif role == LABEL_ROLE_TERSE and not meta.terse_label:
                meta.terse_label = text
            elif role == LABEL_ROLE_DOCUMENTATION and not meta.documentation:
                meta.documentation = text


def _parse_presentation_linkbase(path: Path, index: dict[str, XbrlConceptMeta]) -> None:
    root = ET.parse(path).getroot()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag != "presentationLink":
            continue
        role_uri = _xlink_attr(element, "role")
        statement_role = _infer_statement_role(role_uri)
        locators: dict[str, str] = {}
        for child in element.iter():
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag == "loc":
                label_id = _xlink_attr(child, "label")
                href = _xlink_attr(child, "href")
                if label_id and href:
                    locators[label_id] = concept_local_name(href)
        for child in element.iter():
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag != "loc":
                continue
            label_id = _xlink_attr(child, "label")
            concept = locators.get(label_id)
            if not concept:
                continue
            meta = index.setdefault(concept, XbrlConceptMeta(concept=concept))
            if role_uri and role_uri not in meta.presentation_roles:
                meta.presentation_roles.append(role_uri)
            if meta.statement_role == OTHER and statement_role != OTHER:
                meta.statement_role = statement_role


def _parse_calculation_linkbase(path: Path, index: dict[str, XbrlConceptMeta]) -> None:
    root = ET.parse(path).getroot()
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        if tag != "calculationLink":
            continue
        locators: dict[str, str] = {}
        for child in element.iter():
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag == "loc":
                label_id = _xlink_attr(child, "label")
                href = _xlink_attr(child, "href")
                if label_id and href:
                    locators[label_id] = concept_local_name(href)
        for child in element.iter():
            child_tag = child.tag.rsplit("}", 1)[-1]
            if child_tag != "calculationArc":
                continue
            if _xlink_attr(child, "arcrole") != CALC_ARCROLE:
                continue
            parent = locators.get(_xlink_attr(child, "from"))
            child_concept = locators.get(_xlink_attr(child, "to"))
            if not parent or not child_concept:
                continue
            parent_meta = index.setdefault(parent, XbrlConceptMeta(concept=parent))
            child_meta = index.setdefault(child_concept, XbrlConceptMeta(concept=child_concept))
            if child_concept not in parent_meta.calc_children:
                parent_meta.calc_children.append(child_concept)
            if parent not in child_meta.calc_parents:
                child_meta.calc_parents.append(parent)


def _finalize_metric_roles(index: dict[str, XbrlConceptMeta]) -> None:
    for meta in index.values():
        label = meta.standard_label or meta.terse_label
        meta.metric_roles = _infer_roles_from_label_text(label) if label else []


def build_taxonomy_index(taxonomy_dir: Path) -> dict[str, XbrlConceptMeta]:
    """Parse label/presentation/calculation linkbases under a taxonomy directory."""
    if not taxonomy_dir.is_dir():
        return {}
    index: dict[str, XbrlConceptMeta] = {}
    for path in sorted(taxonomy_dir.glob("*.xml")):
        name = path.name.lower()
        if name.endswith("_lab.xml"):
            _parse_label_linkbase(path, index)
        elif name.endswith("_pre.xml"):
            _parse_presentation_linkbase(path, index)
        elif name.endswith("_cal.xml"):
            _parse_calculation_linkbase(path, index)
    _finalize_metric_roles(index)
    return index


def taxonomy_meta_from_properties(properties: dict | None) -> XbrlConceptMeta | None:
    """Rehydrate taxonomy metadata stored on graph XBRL fact node properties."""
    if not properties:
        return None
    concept = str(properties.get("xbrl_concept") or "")
    label = str(properties.get("xbrl_standard_label") or "")
    if not concept and not label:
        return None
    roles_raw = properties.get("xbrl_metric_roles") or []
    if isinstance(roles_raw, str):
        roles = [r.strip() for r in roles_raw.split(",") if r.strip()]
    else:
        roles = list(roles_raw)
    parents_raw = properties.get("xbrl_calc_parents") or []
    if isinstance(parents_raw, str):
        parents = [p.strip() for p in parents_raw.split(",") if p.strip()]
    else:
        parents = list(parents_raw)
    children_raw = properties.get("xbrl_calc_children") or []
    if isinstance(children_raw, str):
        children = [c.strip() for c in children_raw.split(",") if c.strip()]
    else:
        children = list(children_raw)
    if not any((label, roles, parents, children)):
        return None
    return XbrlConceptMeta(
        concept=concept,
        standard_label=label,
        terse_label=str(properties.get("xbrl_terse_label") or ""),
        documentation=str(properties.get("xbrl_documentation") or ""),
        statement_role=str(properties.get("xbrl_statement_role") or OTHER),
        calc_parents=parents,
        calc_children=children,
        metric_roles=roles,
    )


def taxonomy_properties_for_node(meta: XbrlConceptMeta) -> dict[str, str]:
    """Graph node properties derived from taxonomy metadata (scalar values only)."""
    props: dict[str, str] = {}
    if meta.standard_label:
        props["xbrl_standard_label"] = meta.standard_label
    if meta.terse_label:
        props["xbrl_terse_label"] = meta.terse_label
    if meta.documentation:
        props["xbrl_documentation"] = meta.documentation
    if meta.statement_role and meta.statement_role != OTHER:
        props["xbrl_statement_role"] = meta.statement_role
    if meta.metric_roles:
        props["xbrl_metric_roles"] = ",".join(meta.metric_roles)
    if meta.calc_parents:
        props["xbrl_calc_parents"] = ",".join(meta.calc_parents)
    if meta.calc_children:
        props["xbrl_calc_children"] = ",".join(meta.calc_children)
    return props
