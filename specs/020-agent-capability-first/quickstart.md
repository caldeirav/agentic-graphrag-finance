# Quickstart: Agent Capability-First (020)

## Prerequisites

- Branch `019-agent-failure-investigation` with feature 020 implemented
- Graph snapshots and paper-v1.1 manifest
- API keys for live LLM (or `USE_MOCK_LLM=1` for unit tests only)

## 1. Run unit tests

```bash
uv run pytest tests/unit/test_structured_answer.py \
  tests/unit/test_xbrl_fact_resolution.py \
  tests/unit/test_macro_temporal_hints.py \
  tests/regression/failure_modes/test_no_template_dump_live.py -q
```

## 2. XBRL numeric cohort (26 items)

Cohort file (committed fixture):

`specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json`

### Replay vs re-run (important)

| Mode | Flag | What runs | Validates 020 code? |
|------|------|-----------|---------------------|
| **Replay** | `--replay-input reports/repro-paper-v1.1` | Reads existing `results.json` only | **No** — shows old answers/judge scores |
| **Re-run** | omit `--replay-input` | Live agent on 26 cohort items | **Yes** — uses current synthesis/skills |

Your output (`mode: replay`, empty `synthesis_path`, 18× `template_dump`, outcome=0.000) matches the **pre-fix** paper-v1.1 run. Example answer still starts with `Based on 3 evidence chunk(s)...`.

### Re-run cohort (validate 020 fixes)

```bash
uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --variant graph-full \
  --output reports/cohort-xbrl-numeric-debug \
  --no-resume
```

Requires graph snapshots + LLM API keys. Expect ~26 live queries.

### Replay baseline (compare before/after)

Use only to inspect the **old** run without re-querying:

```bash
uv run agent-query repro cohort-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --cohort specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --replay-input reports/repro-paper-v1.1 \
  --variant graph-full \
  --output reports/cohort-xbrl-numeric-replay-baseline \
  --no-resume
```

Review chunk-dump share on a **re-run** output:

```bash
rg -c "Based on [0-9]+ evidence chunk" reports/cohort-xbrl-numeric-debug/graph-full/ || true
```

Or inspect per-item summaries:

```bash
rg -l template_dump reports/cohort-xbrl-numeric-debug/cohort_debug/ || true
```

## 3. Judge the re-run

The cohort **re-run already judges inline** (`defer_judge=False`), so items show `judge_status: ok` immediately.  
`run-all --judge-only` skips them (`force_rescore=False`).

To **re-score** (e.g. after editing answers or judge config), use `judge-batch --force-rescore`.  
For **paper-v1.1**, the manifest points at unpublished `v2.0.1`; the CLI resolves the quality draft automatically (same as `repro run-all`).

```bash
uv run agent-query repro judge-batch \
  --input reports/cohort-xbrl-numeric-debug \
  --manifest releases/paper-v1.1/manifest.yaml \
  --variant graph-full \
  --item-ids-file specs/020-agent-capability-first/fixtures/xbrl_numeric_cohort.json \
  --force-rescore
```

If bundle resolution fails, pass the draft explicitly:

```bash
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1
```

Inspect `reports/cohort-xbrl-numeric-debug/graph-full/results.json` for per-item `outcome_score` / `judge_verdict.scores.value_alignment`.

## 4. Full repro (after cohort gate)

Only after chunk-dump rate ≤2/26 and VA improvement:

```bash
uv run agent-query repro run-all --manifest releases/paper-v1.1/manifest.yaml
```

## Design reference

- Spec: [spec.md](./spec.md)
- Capability-first rule: `.cursor/rules/agent-capability-first.mdc`
- Constitution Principle VII: `.specify/memory/constitution.md`
