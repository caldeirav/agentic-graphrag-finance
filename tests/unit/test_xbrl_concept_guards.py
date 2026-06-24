"""Unit tests for XBRL concept guards (022)."""

from __future__ import annotations

from retrieval.skills.metric_intent import MetricIntent
from retrieval.skills.xbrl_concept_guards import concept_passes_guard, query_concept_family


def test_equity_guard_rejects_equity_other() -> None:
    assert concept_passes_guard("StockholdersEquityOther", "equity") is False
    assert concept_passes_guard(
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        "equity",
    ) is True


def test_tax_rate_guard_rejects_accrued_taxes() -> None:
    assert concept_passes_guard("AccruedIncomeTaxesCurrent", "tax_rate") is False
    assert concept_passes_guard("IncomeTaxExpenseBenefit", "tax_rate") is True


def test_dividend_payout_guard_rejects_oci() -> None:
    assert (
        concept_passes_guard(
            "OtherComprehensiveIncomeLossReclassificationAdjustmentFromAOCIPension",
            "dividend_payout",
        )
        is False
    )


def test_tax_rate_guard_rejects_statutory_reconciliation() -> None:
    assert concept_passes_guard("IncomeTaxReconciliationIncomeTaxExpenseAtFederalStatutoryRate", "tax_rate") is False


def test_query_concept_family_effective_tax_rate() -> None:
    intent = MetricIntent(metric_type="ratio", metric_label="rate")
    family = query_concept_family("What was the effective tax rate for fiscal year 2025?", intent)
    assert family == "tax_rate"
