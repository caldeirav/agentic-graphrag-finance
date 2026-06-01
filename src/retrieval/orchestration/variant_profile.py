"""Declarative ablation capability profiles for reproduction variants (012)."""

from __future__ import annotations

from pathlib import Path

from evaluation.reproduction.manifest import load_system_variant
from models.reproduction import VariantCapabilities


def load_variant_capabilities(config_path: Path) -> VariantCapabilities:
    return load_system_variant(config_path).capabilities


def variant_metadata_flags(caps: VariantCapabilities) -> dict[str, str]:
    return {
        "variant_disable_macro_router": str(caps.disable_macro_router).lower(),
        "variant_disable_graph_walker": str(caps.disable_graph_walker).lower(),
        "variant_xbrl_only": str(caps.xbrl_only).lower(),
    }
