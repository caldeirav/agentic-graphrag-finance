from pathlib import Path

from parsing.docling_xbrl import (
    find_taxonomy_dir,
    is_xbrl_instance_path,
)


def test_is_xbrl_instance_path():
    assert is_xbrl_instance_path(Path("aapl-20240928_htm.xml"))
    assert not is_xbrl_instance_path(Path("aapl-20240928_cal.xml"))
    assert not is_xbrl_instance_path(Path("filing.html"))


def test_find_taxonomy_dir_uses_fixture_package(fixtures_downloads_root):
    root = fixtures_downloads_root / "AAPL" / "0000320193-24-000123"
    instance = root / "000032019324000123_htm.xml"
    tax = find_taxonomy_dir(root, instance)
    assert (tax / "000032019324000123.xsd").is_file()


def test_find_taxonomy_dir_prefers_xbrl_extracted(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    extracted = root / "xbrl_extracted"
    extracted.mkdir()
    (extracted / "co-20250101.xsd").write_text("<schema/>")
    (root / "co-20250101_htm.xml").write_text("<xbrl/>" * 200)
    (root / "filing-xbrl.zip").write_bytes(b"PK\x05\x06" + b"\x00" * 16)
    instance = root / "co-20250101_htm.xml"
    assert find_taxonomy_dir(root, instance) == extracted
