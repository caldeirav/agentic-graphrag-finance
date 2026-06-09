"""Semver helpers for custom-judge bundle v2 detection (017)."""

from __future__ import annotations

import re

from models.benchmark_generation import DatasetManifest


def parse_semver(version: str) -> tuple[int, int, int]:
    cleaned = version.lstrip("v").strip()
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", cleaned)
    if not match:
        return (0, 0, 0)
    return (int(match.group(1)), int(match.group(2)), int(match.group(3)))


def is_v2_or_later(version: str) -> bool:
    return parse_semver(version)[0] >= 2


def is_v2_bundle(manifest: DatasetManifest | str) -> bool:
    if isinstance(manifest, str):
        return is_v2_or_later(manifest)
    if is_v2_or_later(manifest.schema_version):
        return True
    return is_v2_or_later(manifest.version)
