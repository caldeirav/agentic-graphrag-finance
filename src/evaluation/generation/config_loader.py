"""Load and validate custom-judge generation YAML configs (012)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from models.benchmark_generation import GenerationConfig, IssuerAllowlist

QUOTA_SUM_TOLERANCE = 0.01


class GenerationConfigError(ValueError):
    """Invalid generation config or missing referenced artifacts."""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _resolve_path(path: str | Path, *, base: Path | None = None) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    root = base or _repo_root()
    return (root / candidate).resolve()


def _sha256_canonical_json(data: object) -> str:
    body = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def compute_config_hash(config: GenerationConfig) -> str:
    payload = config.model_dump(mode="json")
    return _sha256_canonical_json(payload)


def load_allowlist(path: str | Path, *, base: Path | None = None) -> IssuerAllowlist:
    resolved = _resolve_path(path, base=base)
    if not resolved.is_file():
        msg = f"Allowlist not found: {resolved}"
        raise GenerationConfigError(msg)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    allowlist = IssuerAllowlist.model_validate(data)
    expected = _sha256_canonical_json(
        {
            "allowlist_id": allowlist.allowlist_id,
            "entries": [e.model_dump(exclude_none=True) for e in allowlist.entries],
        }
    )
    if allowlist.content_hash != expected:
        msg = f"Allowlist content_hash mismatch for {resolved}"
        raise GenerationConfigError(msg)
    return allowlist


def allowlist_hash(path: str | Path, *, base: Path | None = None) -> str:
    return load_allowlist(path, base=base).content_hash


def _validate_judge_config(path: Path) -> None:
    if not path.is_file():
        msg = f"Judge config not found: {path}"
        raise GenerationConfigError(msg)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Judge config must be a mapping: {path}"
        raise GenerationConfigError(msg)
    if not (data.get("model_id") or data.get("model")):
        msg = f"Judge config missing model_id/model field: {path}"
        raise GenerationConfigError(msg)


def _validate_quotas(quotas: dict[str, float]) -> None:
    total = sum(quotas.values())
    if abs(total - 1.0) > QUOTA_SUM_TOLERANCE:
        msg = f"profile_quotas must sum to 1.0 ± {QUOTA_SUM_TOLERANCE}, got {total}"
        raise GenerationConfigError(msg)


def _normalize_raw_config(raw: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(raw)
    inspiration = normalized.pop("inspiration_profiles", None)
    if inspiration is not None:
        normalized["inspiration_profile_paths"] = inspiration
    if "inspiration_profile_paths" not in normalized:
        msg = "Missing inspiration_profiles or inspiration_profile_paths"
        raise GenerationConfigError(msg)
    return normalized


def load_generation_config(
    path: str | Path,
    *,
    base: Path | None = None,
) -> GenerationConfig:
    """Load YAML config, validate quotas, allowlist, and judge config paths."""
    resolved = _resolve_path(path, base=base)
    if not resolved.is_file():
        msg = f"Generation config not found: {resolved}"
        raise GenerationConfigError(msg)
    raw = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"Generation config must be a mapping: {resolved}"
        raise GenerationConfigError(msg)
    config = GenerationConfig.model_validate(_normalize_raw_config(raw))
    _validate_quotas(config.profile_quotas)
    if config.issuer_sample_count > config.governance.max_issuers:
        msg = (
            f"issuer_sample_count ({config.issuer_sample_count}) "
            f"exceeds governance.max_issuers ({config.governance.max_issuers})"
        )
        raise GenerationConfigError(msg)
    root = base or _repo_root()
    load_allowlist(config.allowlist_path, base=root)
    for profile_path in config.inspiration_profile_paths.values():
        profile_resolved = _resolve_path(profile_path, base=root)
        if not profile_resolved.is_file():
            msg = f"Inspiration profile not found: {profile_resolved}"
            raise GenerationConfigError(msg)
    _validate_judge_config(_resolve_path(config.generation_judge_config, base=root))
    _validate_judge_config(_resolve_path(config.evaluation_judge_config, base=root))
    return config
