"""Unit tests for variant profile loading (012)."""

from pathlib import Path

from models.reproduction import VariantCapabilities
from retrieval.orchestration.variant_profile import load_variant_capabilities, variant_metadata_flags


def test_load_graph_full_capabilities() -> None:
    caps = load_variant_capabilities(Path("configs/reproduction/variants/graph-full.yaml"))
    assert caps == VariantCapabilities(
        disable_macro_router=False,
        disable_graph_walker=False,
        xbrl_only=False,
    )


def test_load_ablation_no_macro() -> None:
    caps = load_variant_capabilities(Path("configs/reproduction/variants/ablation-no-macro.yaml"))
    assert caps.disable_macro_router is True
    assert caps.disable_graph_walker is False


def test_load_ablation_no_walker() -> None:
    caps = load_variant_capabilities(Path("configs/reproduction/variants/ablation-no-walker.yaml"))
    assert caps.disable_graph_walker is True


def test_load_ablation_xbrl_only() -> None:
    caps = load_variant_capabilities(Path("configs/reproduction/variants/ablation-xbrl-only.yaml"))
    assert caps.xbrl_only is True


def test_variant_metadata_flags_strings() -> None:
    caps = VariantCapabilities(disable_macro_router=True, xbrl_only=True)
    flags = variant_metadata_flags(caps)
    assert flags == {
        "variant_disable_macro_router": "true",
        "variant_disable_graph_walker": "false",
        "variant_xbrl_only": "true",
    }
