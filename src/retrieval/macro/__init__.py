"""Autonomous macro routing: LLM proposal + deterministic validation."""

from retrieval.macro.models import (
    BindingValidationResult,
    MacroBindingProposal,
    MacroBindingRecord,
    ProposalSource,
    ValidationStatus,
)
from retrieval.macro.pairing import detect_quarterly_metric_cue
from retrieval.macro.planner import plan_macro_binding
from retrieval.macro.validator import validate_macro_binding

__all__ = [
    "BindingValidationResult",
    "MacroBindingProposal",
    "MacroBindingRecord",
    "ProposalSource",
    "ValidationStatus",
    "detect_quarterly_metric_cue",
    "plan_macro_binding",
    "validate_macro_binding",
]
