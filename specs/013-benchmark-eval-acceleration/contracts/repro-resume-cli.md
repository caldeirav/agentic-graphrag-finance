# Reproduction Resume & Recovery CLI Contract (013)

**Extends**: [012 reproduction-cli.md](../../012-research-repro-kit/contracts/reproduction-cli.md)

## New / changed flags

### `run-all`, `run`

| Flag | Default | Notes |
|------|---------|-------|
| `--defer-judge` | false | Enable deferred judging (or env `REPRO_DEFER_JUDGE=1`) |
| `--resume` | **true** | Skip completed variants/items |
| `--no-resume` | — | Fresh run; documented wipe policy |
| `--judge-only` | false | Skip generation; run judge batch only |
| `--export-only` | false | Export tables from existing results |
| `--allow-pending-export` | false | Include partial headline with audit |
| `--judge-batch-after` | `each_variant` | `each_variant` \| `all_variants` |

### New subcommand: `judge-batch`

```bash
OFFLINE_BENCHMARK=1 uv run agent-query repro judge-batch \
  --output reports/repro-paper-v1.0 \
  [--variant graph-full] \
  [--concurrency 2]
```

Requires `GOOGLE_API_KEY` for live paper tags (same as 012).

### `export-tables` (implements 012 stub)

```bash
uv run agent-query repro export-tables \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0
```

Reads per-variant `results.json`; respects pending judge exclusion unless `--allow-pending-export`.

## Resume semantics

### Item-level (012, unchanged)

- Per-variant `results.json` append-only by `item_id`.
- Restart continues pending items only.

### Variant-level (013)

Skip variant when:

- `len(results)` == planned item count from manifest split, AND
- If `defer_judge`: zero rows with `judge_status=pending`, AND
- If not defer: all rows have final judge status

### Run-level `repro_run.json`

```json
{
  "repro_run_id": "...",
  "release_tag": "paper-v1.0",
  "defer_judge": true,
  "current_variant": "flat-chunk",
  "completed_variants": ["graph-full"],
  "items_completed": {"graph-full": 200, "flat-chunk": 45},
  "judge_phase_status": "partial",
  "last_error": null,
  "status": "running"
}
```

Updated atomically after each item and on variant completion.

## Recovery playbook (operator)

Documented in `docs/research-reproduction.md`:

1. **Interrupt**: Ctrl+C or kill — partial `results.json` + `repro_run.json` remain valid.
2. **Verify progress**: `jq length` on `reports/.../graph-full/results.json`; read `repro_run.json`.
3. **Resume**: Same `run-all` command with `--resume` (default).
4. **Judge only**: `judge-batch` or `run-all --judge-only` if generation done.
5. **Export only**: `export-tables` or `run-all --export-only`.
6. **Reset one variant**: `rm -rf reports/.../graph-full` and remove variant from `completed_variants` in `repro_run.json` or use `--no-resume` on fresh output dir.

## Output layout (additions)

```text
reports/repro-paper-v1.0/
├── repro_run.json              # EXTENDED checkpoint
├── graph-full/
│   └── results.json            # May contain judge_status=pending mid-run
└── tables/                     # Written after judge complete (or export-only)
```
