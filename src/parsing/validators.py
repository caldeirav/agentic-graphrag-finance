"""Fail-closed validation for parsed documents."""

from __future__ import annotations

from models.parsing import ParsedDocument


class ParseValidationError(Exception):
    """Raised when parse output fails quality gates."""


def validate_parsed_document(
    doc: ParsedDocument,
    *,
    min_confidence: float = 0.5,
    require_tables_for_forms: set[str] | None = None,
) -> None:
    if doc.parse_confidence < min_confidence:
        raise ParseValidationError(
            f"parse_confidence {doc.parse_confidence} below threshold {min_confidence}"
        )
    forms = require_tables_for_forms or {"10-K", "10-Q"}
    if doc.filing.form_type in forms and not doc.tables:
        raise ParseValidationError(
            f"structurally lossy parse: no tables extracted for {doc.filing.form_type}"
        )
