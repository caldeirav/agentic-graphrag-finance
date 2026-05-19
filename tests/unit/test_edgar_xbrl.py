from ingestion.edgar_xbrl import classify_filename, is_xbrl_package_file
from models.ingestion import XBRLArtifactRole


def test_classify_xbrl_filenames():
    assert classify_filename("0000320193-24-000123-xbrl.zip") == XBRLArtifactRole.XBRL_ZIP
    assert classify_filename("aapl-20240928_htm.xml") == XBRLArtifactRole.INSTANCE
    assert classify_filename("aapl-20240928.xsd") == XBRLArtifactRole.SCHEMA
    assert classify_filename("aapl-20240928_cal.xml") == XBRLArtifactRole.CALCULATION
    assert classify_filename("aapl-20240928_pre.xml") == XBRLArtifactRole.PRESENTATION


def test_is_xbrl_package_file():
    assert is_xbrl_package_file("aapl-20240928_htm.xml")
    assert is_xbrl_package_file("0000320193-24-000123-xbrl.zip")
    assert not is_xbrl_package_file("report.css")
