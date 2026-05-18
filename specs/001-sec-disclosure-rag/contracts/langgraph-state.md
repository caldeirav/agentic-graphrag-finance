# LangGraph State Contract

**Package**: `src/retrieval/orchestration/`

## Graph topology

```text
START → macro_router → meso_router → micro_extractor → synthesize → END
                              ↘ (on empty sections) → synthesize (insufficient)
```

## Nodes

| Node | Reads | Writes | LLM |
|------|-------|--------|-----|
| `macro_router` | `query`, graph manifest (filing list) | `macro_plan`, `filing_set` | Qwen via LM Studio |
| `meso_router` | `macro_plan`, `filing_set`, GraphQueryAPI | `section_candidates` | Qwen |
| `micro_extractor` | `section_candidates`, GraphQueryAPI | `evidence_chunks` | Qwen |
| `synthesize` | `evidence_chunks`, `query` | `answer`, `status` | Qwen (optional final polish) |

## Fail-closed rules

1. If `filing_set` empty after macro → `status=INSUFFICIENT_EVIDENCE`
2. If `evidence_chunks` empty after micro → `status=INSUFFICIENT_EVIDENCE`
3. Synthesis MUST NOT introduce numeric literals absent from `evidence_chunks` excerpts

## MLflow hooks

Each node execution logs:
- `node_name`, `duration_ms`, `token_usage` (if available)
- Serialized subset of state delta (no raw full filing text)

Parent run created in `QueryService.answer()` before `graph.invoke()`.
