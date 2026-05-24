# Trajectory Validator Contract (010)

**Feature**: 010-mlflow-trajectory-judge-eval  
**Module**: `evaluation/validator/trajectory.py`  
**Artifact**: `trajectory_validation.json`

## API

```python
def validate_trajectory(snapshot: AgentTrajectorySnapshot) -> TrajectoryValidationResult:
    ...
```

Pure function; no I/O; no MLflow calls inside validator (caller logs result).

## Status enum

| Status | Meaning |
|--------|---------|
| `complete` | All mandatory rules pass; eligible for judge + fidelity aggregates |
| `incomplete` | Missing or invalid mandatory fields |
| `non_reproducible` | Structural inconsistency (orphan hops, accession mismatch) |

## Reason codes (initial set)

| Code | Status | Trigger |
|------|--------|---------|
| `MISSING_SCHEMA_VERSION` | incomplete | |
| `MISSING_PLAN` | incomplete | No plan on successful ask |
| `EMPTY_DOCUMENT_ROUTE` | incomplete | Success path without filings |
| `MISSING_NODE_TYPE` | incomplete | Hop without `node_type` |
| `MISSING_EDGE_TYPE` | incomplete | Hop without `edge_type` |
| `MISSING_CONTENT_HASH` | incomplete | Evidence entry |
| `MISSING_CITATION_LABEL` | incomplete | Evidence entry |
| `ORPHAN_HOP_ACCESSION` | non_reproducible | `node_id` accession ∉ document_route |
| `EVIDENCE_ACCESSION_MISMATCH` | non_reproducible | evidence.accession ∉ route |
| `INVALID_HOP_EDGE` | incomplete | Neither `edge_id` nor allowed `edge_type`-only pattern |
| `MISSING_ABSENT_REASON` | incomplete | Empty traversal/evidence without reason on failed macro |

## Judge interaction

| validation_status | Judge behavior |
|-------------------|----------------|
| `complete` | Run judge (FR-009a) |
| `incomplete` | `judge_status=not_evaluable`, skip |
| `non_reproducible` | `judge_status=not_evaluable`, skip |

## Aggregates (FR-008)

Benchmark runner MUST:
- Include only `complete` items in `mean_scores` and headline fidelity
- Report `incomplete_count`, `non_reproducible_count` separately

## Fixtures

`tests/fixtures/trajectory_validation/`:
- `valid_complete.json`
- `missing_hashes.json` → incomplete
- `orphan_hop.json` → non_reproducible
- `macro_failed_with_reason.json` → complete

## Contract tests

`tests/contract/test_trajectory_validator.py` — table-driven over fixtures
