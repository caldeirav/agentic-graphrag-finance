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
    "ReportInputError",
    "ReportRenderError",
    "load_release_manifest",
    "load_repro_report_bundle",
    "render_html_report",
    "render_latex_only",
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
    if name == "ReportInputError":
        from evaluation.reproduction.report_errors import ReportInputError

        return ReportInputError
    if name == "ReportRenderError":
        from evaluation.reproduction.report_errors import ReportRenderError

        return ReportRenderError
    if name == "load_repro_report_bundle":
        from evaluation.reproduction.report_loader import load_repro_report_bundle

        return load_repro_report_bundle
    if name == "render_html_report":
        from evaluation.reproduction.report_render import render_html_report

        return render_html_report
    if name == "render_latex_only":
        from evaluation.reproduction.report_render import render_latex_only

        return render_latex_only
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
