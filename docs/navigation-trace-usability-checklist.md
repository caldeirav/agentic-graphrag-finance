# Navigation trace usability checklist (009 SC-002)

Manual review template for five representative `agent-query ask` runs with `USE_MOCK_LLM=0` (or mock with verbose trace).

## Per-query checklist

| # | Query (ticker) | Pass? | Notes |
|---|----------------|-------|-------|
| 1 | Risk factors in MD&A (AAPL) | ☐ | |
| 2 | Revenue / net sales table (AAPL) | ☐ | |
| 3 | Footnote on revenue recognition (AAPL) | ☐ | |
| 4 | Multi-period comparison (AAPL, 2+ filings) | ☐ | |
| 5 | Accounting policies in notes (AAPL) | ☐ | |

## Meso stage (`meso_router`)

- [ ] `navigation_mode=graph_native` appears in console trace
- [ ] `edge_types_used` lists only structural types (`CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`)
- [ ] `sample_path` is readable (≤6 hops shown)
- [ ] `top_section_ids` align with query topic (≤3 per filing)
- [ ] `rejected_count` is present when planner proposals fail validation

## Micro stage (`micro_extractor`)

- [ ] `navigation_mode=graph_native`
- [ ] `sample_path` shows path to at least one cited chunk
- [ ] Ranked evidence rows include `chunk_node_id` and structural path (verbose)
- [ ] No heuristic-only routing fields (legacy `rank_sections_heuristic` absent)

## Trajectory artifact (MLflow)

- [ ] `navigation_trace.json` present on run
- [ ] `meso_paths` / `micro_paths` include `edge_type_sequence`
- [ ] `scan_ratio` < 0.90 for normal queries (no full-graph scan before answer)

## Failure signals

- [ ] Budget exhausted → `budget_exhausted=true` and explicit stage summary
- [ ] Empty evidence → status `INSUFFICIENT_EVIDENCE`, not silent fallback

## Sign-off

Reviewer: _______________  Date: _______________  Build / commit: _______________
