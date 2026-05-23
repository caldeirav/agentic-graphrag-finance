# Contract: Hop Proposal & Validator (009)

**Feature**: 009-graph-native-meso-micro | **Version**: 1.0.0

## Planner API

```python
def propose_next_hop(
    *,
    stage: Literal["meso", "micro"],
    query: str,
    snapshot_id: str,
    source_node_id: str,
    neighbor_summary: list[NeighborSummary],  # from graph API, structural only
    filing_set: list[FilingRef],
    prior_visits: list[NavigationVisit],
) -> HopProposal: ...
```

**LLM output schema** (`HopProposal`):

```json
{
  "stage": "meso",
  "source_node_id": "doc-0000320193-26-000006",
  "candidates": [
    {
      "target_node_id": "sec-item-7",
      "edge_type": "CONTAINS",
      "direction": "outgoing",
      "score": 0.92
    }
  ],
  "intent_note": "MD&A section for risk discussion"
}
```

**Mock mode** (`USE_MOCK_LLM=1`): load fixture JSON by scenario key; no network.

## Validator API

```python
def validate_hop_proposal(
    *,
    proposal: HopProposal,
    snapshot: GraphSnapshot,
    filing_accessions: set[str],
    budgets: NavigationBudgetState,
) -> HopValidationResult: ...
```

## Validation rules (ordered)

1. `len(candidates) <= max_candidates_per_proposal`
2. Each candidate: `edge_type in STRUCTURAL_EDGE_TYPES`
3. Edge exists in snapshot between source and target with matching type/direction
4. Target node’s accession ∈ `filing_accessions`
5. `budgets` has remaining hop/visit quota for stage
6. If no candidate passes, return `rejected` with `rejection_code=no_valid_candidate`

On approval: emit single `NavigationVisit` (highest validator score; tie-break: LLM score, then stable node_id sort).

## Walker loop

```python
def walk_from_root(root_node_id, stage, ...) -> NavigationPath:
    position = root_node_id
    while not done:
        neighbors = graph_api.outgoing_edges(..., STRUCTURAL_EDGE_TYPES)
        proposal = propose_next_hop(...)
        result = validate_hop_proposal(...)
        if result.status == "approved":
            append visit; position = result.approved_hop.target_node_id
        else:
            append to rejected_proposals; break or branch per policy
    return NavigationPath(...)
```

## Rejection codes

| Code | Meaning |
|------|---------|
| `disallowed_edge` | Non-structural edge type |
| `edge_not_found` | No matching edge in snapshot |
| `out_of_scope` | Target accession not in filing set |
| `budget_exceeded` | Hop or visit cap hit |
| `no_valid_candidate` | All candidates failed |
| `invalid_source` | Source node not current position |

## Tests

- `tests/unit/test_navigation_validator.py` — all rejection codes
- `tests/unit/test_navigation_validator_scope.py` — cross-accession reject
- `tests/contract/test_navigation_layer_boundaries.py` — eval does not import planner
