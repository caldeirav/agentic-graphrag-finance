# Macro Binding Validator Contract (008)

**Feature**: 008-autonomous-macro-routing | **Module**: `src/retrieval/macro/validator.py`

## API

```python
def validate_macro_binding(
    proposal: MacroBindingProposal,
    snapshot: GraphSnapshot,
    *,
    cli_bound: list[FilingRef] | None = None,
    query: str = "",
) -> BindingValidationResult:
    ...
```

## Inputs

| Input | Role |
|-------|------|
| `proposal` | LLM or deterministic proposal (untrusted) |
| `snapshot` | Authoritative `filing_refs` |
| `cli_bound` | Non-empty when CLI resolved scope before graph |
| `query` | For quarterly-metric cue detection (`revenue`, `sales`, etc.) |

## Outputs

| `status` | `filing_set` behavior |
|----------|----------------------|
| `approved` | Use `approved_accessions` resolved to `FilingRef` |
| `failed` | Empty set; graph short-circuits to scope error response |
| `narrowed` | Single accession; `comparison_mode` forced to `none`; rationale required |

## Pairing resolution

When proposal indicates comparison without explicit accessions, validator **materializes** accessions using manifest ordering (see `research.md` R2). Proposal accessions, if present, must match materialized set or fail `invalid_pairing`.

## CLI precedence

1. If `cli_bound` non-empty: approved set MUST equal `cli_bound` accessions (order-insensitive) unless proposal only adds metadata → still approve CLI set.
2. If proposal accessions ⊄ cli_bound and conflict → `cli_nl_conflict` fail.
3. If `cli_bound` empty: full autonomous validation.

## Failure messages (user-visible)

Must include: failure code, requested comparison/anchor, what was missing from corpus, suggested action (materialize / rephrase / add `--period`).

## Tests (required)

| Test file | Coverage |
|-----------|----------|
| `tests/unit/test_macro_validator.py` | YoY quarterly/annual, QoQ, prior quarter, fail closed, narrow |
| `tests/unit/test_macro_validator_cli_conflict.py` | FR-006 precedence |
| `tests/fixtures/macro_validator/` | Snapshot manifests + proposals |
