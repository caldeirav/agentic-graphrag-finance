"""Unit tests for graph section path resolution (011)."""

from evaluation.generation.section_paths import resolve_section_path


def test_resolve_suffix_and_prefix_accession_mismatch():
    graph_paths = {
        "0000018230-26-000008/Item 1A. Risk Factors",
        "0000320193-26-000006/Item 1A.",
    }
    snapshot = {
        "0000018230-26-000008",
        "0000018230-25-000016",
        "0000320193-26-000006",
    }

    cat = resolve_section_path(
        "0000018230-25-000016/Item 1A. Risk Factors",
        graph_paths,
        snapshot_accessions=snapshot,
    )
    assert cat == "0000018230-26-000008/Item 1A. Risk Factors"

    apple = resolve_section_path(
        "0000320193-26-000006/Item 1A. Risk Factors",
        graph_paths,
        snapshot_accessions=snapshot,
    )
    assert apple == "0000320193-26-000006/Item 1A."


def test_resolve_exact_path():
    graph_paths = {"acc-1/Item7"}
    resolved = resolve_section_path(
        "acc-1/Item7",
        graph_paths,
        snapshot_accessions={"acc-1"},
    )
    assert resolved == "acc-1/Item7"
