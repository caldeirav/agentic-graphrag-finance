"""Shared regeneration feedback prompts for dataset quality review (018)."""

from evaluation.generation.comparison_gt import COMPARISON_ANSWER_PROMPT_RULES

BOILERPLATE_REGEN_FEEDBACK = f"""
The previous canonical answer was rejected as boilerplate (section co-occurrence only).
Regenerate the full item JSON for the same item_id and inspiration profile.

Requirements:
{COMPARISON_ANSWER_PROMPT_RULES}
- expected_section_paths must exist in available_section_paths.
- Preserve multi-filing bindings (>=2 accessions) from the original item when possible.
"""
