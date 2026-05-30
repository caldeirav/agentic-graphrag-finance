# System Variant Config Contract (012)

**Artifacts**: `configs/reproduction/variants/{variant_id}.yaml`

## graph-full.yaml

```yaml
variant_id: graph-full
description: Production graph-grounded agent (all stages enabled)
backend: langgraph
capabilities:
  disable_macro_router: false
  disable_graph_walker: false
  xbrl_only: false
```

## flat-chunk.yaml

```yaml
variant_id: flat-chunk
description: Dense embedding RAG over frozen corpus chunks (no graph navigation)
backend: flat_chunk
top_k: 10
embedding_cache_subdir: chunk_embeddings/all-MiniLM-L6-v2
capabilities: {}  # N/A — handled by FlatChunkBaseline
```

## ablation-no-macro.yaml

```yaml
variant_id: ablation-no-macro
description: Graph agent without macro router (pre-bound filings only)
backend: langgraph
capabilities:
  disable_macro_router: true
  disable_graph_walker: false
  xbrl_only: false
```

## ablation-no-walker.yaml

```yaml
variant_id: ablation-no-walker
description: Graph agent without meso/micro graph walker hops
backend: langgraph
capabilities:
  disable_macro_router: false
  disable_graph_walker: true
  xbrl_only: false
```

## ablation-xbrl-only.yaml

```yaml
variant_id: ablation-xbrl-only
description: Graph agent excluding HTML narrative supplement chunks
backend: langgraph
capabilities:
  disable_macro_router: false
  disable_graph_walker: false
  xbrl_only: true
```

## Runtime wiring

- **LangGraph variants**: `QueryRequest.metadata["variant_profile"]` carries parsed `VariantCapabilities`; `build_agent_graph(..., variant_profile=...)` conditionally skips stages or filters chunk sources.
- **flat-chunk**: `EvaluationReproRunner` invokes `FlatChunkBaseline.answer(item)` — does NOT call `QueryService.answer`.

## Paper-v1.0 required set

All five files MUST exist; release manifest `variant_ids` MUST reference these ids in order.
