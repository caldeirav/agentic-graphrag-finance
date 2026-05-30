# Reproduction CLI Contract (012)

**Entry point**: `uv run agent-query repro`

## Subcommands

| Command | Purpose |
|---------|---------|
| `verify-corpus` | Hash-check LFS corpus vs release + 011 manifest |
| `materialize-relevance` | Derive `relevant_chunk_ids` (see relevance-materialize.md) |
| `run` | Execute one or all variants from manifest |
| `export-tables` | Aggregate completed variant runs → paper CSV/TeX |
| `verify-tables` | Compare exports to `expected_checksums.json` with tolerance bands |
| `run-all` | `verify-corpus` → relevance gate → all variants → `export-tables` |

## `run-all` (primary reproduction path)

```bash
OFFLINE_BENCHMARK=1 uv run agent-query repro run-all \
  --manifest releases/paper-v1.0/manifest.yaml \
  --output reports/repro-paper-v1.0
```

### Flags

| Flag | Default | Notes |
|------|---------|-------|
| `--manifest` | required | Path to release manifest YAML |
| `--output` | `reports/repro-{tag}` | Table + per-variant report root |
| `--variants` | all in manifest | Comma-separated subset (smoke) |
| `--max-items` | none | Cap items (CI smoke only) |
| `--strict-git` | true for paper-v1.0 | Fail if HEAD ≠ manifest git_sha |
| `--skip-relevance` | false | Require pre-materialized labels |

### Environment

| Variable | Required | Notes |
|----------|----------|-------|
| `OFFLINE_BENCHMARK=1` | yes | Hard fail on EDGAR network (FR-002) |
| `USE_MOCK_JUDGE=1` | CI only | Smoke path |
| `USE_MOCK_LLM=1` | CI only | Smoke path |
| `GOOGLE_API_KEY` | live repro | When judge pin is Gemini |
| LM Studio vars | live repro | When LLM pin is local |

## Offline enforcement

`verify-corpus` and `run` MUST set or require `OFFLINE_BENCHMARK=1`. Integration test patches network and asserts zero EDGAR host calls (SC-005).

## Output layout

```text
reports/repro-paper-v1.0/
├── repro_run.json
├── graph-full/
│   └── benchmark-{id}/summary.json
├── flat-chunk/
│   └── …
├── ablation-no-macro/
├── ablation-no-walker/
├── ablation-xbrl-only/
└── tables/
    ├── headline.csv
    ├── by_profile.csv
    ├── variant_delta.csv
    ├── trajectory_audit.csv
    └── headline.tex
```

## Registry scope (FR-003)

`run` MUST load **only** `custom-judge` dataset adapter. Upstream `finder`, `financebench`, `finagentbench` adapters MUST NOT be invoked.
