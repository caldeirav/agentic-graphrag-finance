from pathlib import Path


def test_no_sidecar_html_parse_files_in_repo_contract() -> None:
    parsed_root = Path("data/parsed")
    if not parsed_root.exists():
        return
    sidecars = list(parsed_root.rglob("*-html.json"))
    assert sidecars == [], f"sidecar HTML parses not allowed: {sidecars}"
