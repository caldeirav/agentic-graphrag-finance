# Judge Generation Layer Boundary Contract (012)

**Goal**: Dataset generation stays in the **evaluation** layer without importing **agentic retrieval** internals.

## Allowed dependencies

| From | May import / call |
|------|-------------------|
| `evaluation/generation/*` | `models.*`, `evaluation/judges/*` (client only), `graph.store` (read-only index for validation), stdlib |
| `cli/commands/benchmark_dataset.py` | `evaluation/generation/*`, **`cli.corpus_pipeline.run_materialize_pipeline`**, `ingestion.settings` |

## Forbidden imports (build failure in contract tests)

Modules under `src/evaluation/generation/` MUST NOT import:

- `retrieval.service`
- `retrieval.orchestration.*`
- `ingestion.edgar_client` (direct fetch — materialize CLI only)
- `graph.builder` (direct build — use corpus pipeline)

## Materialization facade

```text
benchmark_dataset.generate
  → evaluation.generation.sampler
  → cli.corpus_pipeline.run_materialize_pipeline  (per issuer)
  → evaluation.generation.judge_generator
  → evaluation.generation.item_validator
  → evaluation.generation.bundle
```

## Judge generation vs trajectory judge

| Concern | Module | Prompts |
|---------|--------|---------|
| Item authoring | `evaluation/generation/judge_generator.py` | `configs/benchmarks/inspiration_profiles/*.yaml` |
| Run scoring | `evaluation/judges/gemini_panel.py` | `configs/judges/gemini_2_5_pro.yaml` |

Shared: HTTP client / model id resolution only.

## Test enforcement

`tests/contract/test_generation_import_boundary.py` — static import scan of `evaluation/generation/` (mirror `test_judge_import_boundary.py` from 010).

## Rationale

Constitution Principle IV: evaluation orchestrates benchmarks and external judges; retrieval orchestration remains unchanged when registering/unregistering `custom-judge`.
