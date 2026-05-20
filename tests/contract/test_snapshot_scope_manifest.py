"""SnapshotScopeManifest contract fields."""

from models.corpus import BoundFilingEntry, FiscalPeriodLabel, SnapshotScopeManifest


def test_manifest_required_fields():
    m = SnapshotScopeManifest(
        snapshot_id="abc",
        issuer_id="AAPL",
        bound_filings=[
            BoundFilingEntry(
                accession="0000320193-24-000076",
                form_type="10-Q",
                fiscal_period=FiscalPeriodLabel(fiscal_year=2024, fiscal_quarter=2, label="FY2024-Q2"),
                filed_at=__import__("datetime").date(2024, 8, 2),
            )
        ],
    )
    dumped = m.model_dump(mode="json")
    assert dumped["snapshot_id"]
    assert dumped["issuer_id"]
    assert len(dumped["bound_filings"]) >= 1
    assert "accession" in dumped["bound_filings"][0]
