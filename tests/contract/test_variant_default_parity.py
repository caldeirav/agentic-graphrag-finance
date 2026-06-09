"""Contract test: default variant profile preserves production stage set (012)."""

from evaluation.reproduction.manifest import (
    default_variant_capabilities,
    production_stage_ids_with_profile,
)
from models.reproduction import VariantCapabilities
from retrieval.orchestration.graph import build_agent_graph, get_ask_graph_stage_ids


def test_default_profile_matches_production_stages() -> None:
    default_stages = production_stage_ids_with_profile(default_variant_capabilities())
    assert default_stages == get_ask_graph_stage_ids()


def test_ablation_no_macro_skips_macro_stage() -> None:
    caps = VariantCapabilities(disable_macro_router=True)
    assert "macro_router" not in get_ask_graph_stage_ids(caps)


def test_ablation_no_walker_skips_meso_micro() -> None:
    caps = VariantCapabilities(disable_graph_walker=True)
    stages = get_ask_graph_stage_ids(caps)
    assert "meso_router" not in stages
    assert "micro_extractor" not in stages


def test_build_agent_graph_compiles_for_ablations() -> None:
    for caps in (
        VariantCapabilities(),
        VariantCapabilities(disable_macro_router=True),
        VariantCapabilities(disable_graph_walker=True),
        VariantCapabilities(disable_macro_router=True, disable_graph_walker=True),
    ):
        compiled = build_agent_graph(None, variant_profile=caps)
        assert compiled is not None
