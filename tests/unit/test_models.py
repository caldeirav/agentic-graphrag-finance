from datetime import date

import pytest

from models.filing import FilingRef
from parsing.validators import ParseValidationError, validate_parsed_document


def test_filing_ref_valid():
    f = FilingRef(
        cik="0000320193",
        accession="0000320193-24-000123",
        form_type="10-K",
        filed_at=date(2024, 1, 1),
        period_end=date(2024, 9, 28),
        source_uri="https://example.com",
    )
    assert f.form_type == "10-K"


def test_parse_validation_fails_low_confidence(sample_parsed_document):
    doc = sample_parsed_document.model_copy(update={"parse_confidence": 0.1})
    with pytest.raises(ParseValidationError):
        validate_parsed_document(doc, min_confidence=0.5)


def test_parse_validation_requires_tables_for_10k(sample_parsed_document):
    doc = sample_parsed_document.model_copy(update={"tables": []})
    with pytest.raises(ParseValidationError):
        validate_parsed_document(doc)
