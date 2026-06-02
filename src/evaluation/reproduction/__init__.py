"""Research reproduction kit for paper benchmark runs (012/013).

Heavy exports (``ReproRunner``, ``run_judge_batch``) are lazy so importing
``evaluation.reproduction.defer_config`` from ``retrieval.service`` does not
pull in the runner → QueryService cycle.
"""

from __future__ import annotations

from evaluation.reproduction.defer_config import resolve_defer_config
from evaluation.reproduction.errors import MissingAccessionsError, MissingBindingsError

__all__ = [
    "MissingAccessionsError",
    "MissingBindingsError",
    "ReproRunner",
    "load_release_manifest",
    "resolve_defer_config",
    "run_judge_batch",
]


def __getattr__(name: str) -> object:
    if name == "ReproRunner":
        from evaluation.reproduction.runner import ReproRunner

        return ReproRunner
    if name == "load_release_manifest":
        from evaluation.reproduction.manifest import load_release_manifest

        return load_release_manifest
    if name == "run_judge_batch":
        from evaluation.reproduction.judge_batch import run_judge_batch

        return run_judge_batch
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
