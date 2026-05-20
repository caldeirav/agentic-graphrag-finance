"""Fiscal period labels for non-calendar fiscal years (e.g. Apple Sep FY)."""

from datetime import date

from models.corpus import FiscalPeriodLabel, infer_fiscal_year_end_month
from models.filing import FilingRef


def _ref(*, form_type: str, period_end: date) -> FilingRef:
    return FilingRef(
        cik="0000320193",
        accession="0000320193-26-000013",
        form_type=form_type,
        filed_at=date(2026, 5, 1),
        period_end=period_end,
        source_uri="https://example.com",
    )


def test_infer_fiscal_year_end_from_10k():
    refs = [
        _ref(form_type="10-K", period_end=date(2025, 9, 27)),
        _ref(form_type="10-Q", period_end=date(2026, 3, 28)),
    ]
    assert infer_fiscal_year_end_month(refs) == 9


def test_apple_fy2026_q2_label():
    ref = _ref(form_type="10-Q", period_end=date(2026, 3, 28))
    label = FiscalPeriodLabel.from_filing(ref, fiscal_year_end_month=9)
    assert label.label == "FY2026-Q2"


def test_apple_fy2026_q1_prior_quarter_label():
    ref = _ref(form_type="10-Q", period_end=date(2025, 12, 27))
    label = FiscalPeriodLabel.from_filing(ref, fiscal_year_end_month=9)
    assert label.label == "FY2026-Q1"
