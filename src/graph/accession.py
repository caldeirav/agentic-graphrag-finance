"""Accession helpers for graph node ids."""

from __future__ import annotations

import re

_DOC_ACCESSION = re.compile(r"doc-(\d{10}-\d{2}-\d{6})")


def accession_from_node_id(node_id: str) -> str:
    m = _DOC_ACCESSION.search(node_id)
    if m:
        return m.group(1)
    # Legacy builder uses doc-{accession} with hyphens preserved
    if node_id.startswith("doc-") and len(node_id) > 4:
        return node_id[4:]
    return ""


def document_root_id(accession: str) -> str:
    return f"doc-{accession}" if accession else ""
