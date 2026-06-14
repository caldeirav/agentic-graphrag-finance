"""Load and validate release manifests (012)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import yaml

from models.reproduction import (
    ReleaseManifest,
    SystemVariantConfig,
    VariantCapabilities,
)


def resolve_release_manifest_path(release_tag: str, *, repo_root: Path | None = None) -> Path:
    """Resolve releases/{release_tag}/manifest.yaml from repo root."""
    root = repo_root or Path.cwd()
    path = root / "releases" / release_tag / "manifest.yaml"
    if not path.is_file():
        msg = f"Release manifest not found: {path}"
        raise FileNotFoundError(msg)
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"sha256:{digest}"


def sha256_text(text: str) -> str:
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def load_release_manifest(path: Path, *, strict_paper_v1: bool = False) -> ReleaseManifest:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    manifest = ReleaseManifest.model_validate(raw)
    if strict_paper_v1 or manifest.release_tag == "paper-v1.0":
        manifest.validate_paper_v1()
    return manifest


def load_system_variant(config_path: Path) -> SystemVariantConfig:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return SystemVariantConfig.model_validate(raw)


def resolve_variant_configs(
    manifest: ReleaseManifest,
    variants_root: Path | None = None,
) -> list[SystemVariantConfig]:
    root = variants_root or Path("configs/reproduction/variants")
    out: list[SystemVariantConfig] = []
    for variant_id in manifest.variant_ids:
        path = root / f"{variant_id}.yaml"
        if not path.is_file():
            msg = f"Missing variant config: {path}"
            raise FileNotFoundError(msg)
        cfg = load_system_variant(path)
        if cfg.variant_id != variant_id:
            msg = f"Variant id mismatch: {path} has {cfg.variant_id}, manifest expects {variant_id}"
            raise ValueError(msg)
        out.append(cfg)
    return out


def load_expected_checksums(manifest_path: Path, manifest: ReleaseManifest) -> dict:
    checksums_path = manifest_path.parent / manifest.expected_checksums_path
    if not checksums_path.is_file():
        return {}
    return json.loads(checksums_path.read_text(encoding="utf-8"))


def enforce_max_items_policy(
    manifest: ReleaseManifest,
    max_items: int | None,
    *,
    item_ids: list[str] | None = None,
) -> None:
    if item_ids:
        return
    if manifest.release_tag in {"paper-v1.0", "paper-v2.0"} and max_items is not None:
        msg = (
            f"{manifest.release_tag} repro does not allow --max-items; "
            "use releases/paper-v2.0-smoke/manifest.yaml for agent iteration"
        )
        raise ValueError(msg)


def enforce_full_repro_policy(
    manifest: ReleaseManifest,
    *,
    max_items: int | None = None,
    item_ids: list[str] | None = None,
    variant_count: int | None = None,
) -> None:
    """Block accidental full paper-v2.0 locks during agent iteration."""
    if manifest.release_tag != "paper-v2.0":
        return
    if os.environ.get("REPRO_ALLOW_FULL", "").strip().lower() in {"1", "true", "yes"}:
        return
    policy = manifest.full_reproduction_policy
    required_variants = policy.required_variants if policy else 5
    required_items = policy.required_items_per_variant if policy else 200
    if variant_count is not None and variant_count >= required_variants:
        if max_items is None and not item_ids:
            msg = (
                "Full paper-v2.0 reproduction (5 variants × 200 items) is frozen for agent "
                "iteration. Use `agent-query repro smoke-run` or set REPRO_ALLOW_FULL=1 "
                "when locking expected_checksums."
            )
            raise ValueError(msg)
    if max_items is not None and max_items < required_items:
        msg = (
            f"paper-v2.0 run-all with --max-items {max_items} is not allowed; "
            "use releases/paper-v2.0-smoke/manifest.yaml"
        )
        raise ValueError(msg)


def default_variant_capabilities() -> VariantCapabilities:
    return VariantCapabilities()


def production_stage_ids_with_profile(profile: VariantCapabilities | None) -> set[str]:
    """Stage set for a variant profile — used by parity contract test."""
    profile = profile or default_variant_capabilities()
    stages = {
        "macro_router",
        "intent_router",
        "meso_router",
        "micro_extractor",
        "synthesize",
    }
    if profile.disable_macro_router:
        stages.discard("macro_router")
    if profile.disable_graph_walker:
        stages -= {"meso_router", "micro_extractor"}
    return stages
