# Quickstart: Custom-Judge Bundle v2.0 and paper-v2.0 (017)

**Feature**: 017-custom-judge-v2 | **Date**: 2026-06-02

## Prerequisites

- `uv sync --locked`
- `.env` with `GOOGLE_API_KEY`, `SEC_EDGAR_USER_AGENT`
- Git LFS installed
- Branch `017-custom-judge-v2` with plan artifacts merged
- v1.2.0 bundle present for lineage audit only (not imported)

## Phase 1 — Generate net-new v2.0 draft

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-20260602 \
  --bundle-version 2.0.0
```

Review outputs under `data/benchmarks/custom-judge/drafts/v2-draft-20260602/`:

| Report | Acceptance |
|--------|------------|
| `generation_report.json` | `pass_rate` ≥ 0.95, `accepted_count` ≥ 200 |
| `feasibility_report.json` | `blocked_count: 0`, `macro_bindability_failures: 0` |
| `scorability_report.json` | `answer_gt_coverage: 1.0`, `rubric_only_count: 0` |
| `multi_filing_count` | ≥ 40 |

## Phase 2 — Operator audit (10%)

1. Open `publish_audit.sample.json` — 20 stratified item ids.
2. For each item verify: question clarity, answer-GT correctness, claims atomicity, bindings feasible.
3. Record notes; fix blocked items in draft or regenerate backfill if needed.

## Phase 3 — Publish v2.0.0

```bash
uv run agent-query benchmark-dataset publish \
  --draft-run-id v2-draft-20260602 \
  --version 2.0.0 \
  --publish-signoff \
  --operator-id "${USER}"
```

Verify:
- `data/benchmarks/custom-judge/v2.0.0/manifest.json` → `version: "2.0.0"`, `parent_version: "1.2.0"`
- v1.2.0 directory unchanged: `git diff data/benchmarks/custom-judge/v1.2.0`

## Phase 4 — paper-v2.0 release lock

```bash
# After copying releases/paper-v2.0/manifest.yaml template and filling hashes:
uv run agent-query repro materialize-relevance --release paper-v2.0
```

Commit `releases/paper-v2.0/manifest.yaml` with pinned `items_hash`, `corpus_hashes`, `relevance_labels_hash`.

## Phase 5 — Full reproduction (five variants × 200 items)

```bash
export USE_MOCK_LLM=0 USE_MOCK_JUDGE=0
uv run agent-query repro run --release paper-v2.0 --tag paper-v2.0
uv run agent-query repro judge-batch --input reports/repro-paper-v2.0
uv run agent-query repro export-tables --input reports/repro-paper-v2.0
uv run agent-query repro report --input reports/repro-paper-v2.0
```

**No selective skip**: every item runs on every variant.

## Phase 6 — Verify unified task_success

Inspect `reports/repro-paper-v2.0/tables/headline.csv` (or JSON export):

| Check | Expected |
|-------|----------|
| `task_success` item_count | 200 |
| `task_success` value | mean value_alignment |
| `rubric_alignment` row | absent |
| MRR / nDCG@10 | present; definitions unchanged |

Open `report.html` — headline section shows task_success as sole outcome metric.

## Phase 7 — Third-party reproduce (offline)

```bash
git lfs pull --include="data/benchmarks/custom-judge/v2.0.0/corpus/**"
OFFLINE_BENCHMARK=1 uv run agent-query benchmark-dataset reproduce \
  --version 2.0.0 \
  --verify-lfs
```

Expect matching `items_hash` and corpus content hashes.

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `multi_filing_floor` gate fails | Increase finagentbench quota in v2 config; regenerate |
| `macro_bindability` failures | Fix bindings or drop item; verify corpus has comparison partners |
| task_success n < 200 | Check headline eligibility; v2 items must all have answer GT |
| rubric_alignment in v2 report | Verify release manifest pins `2.0.0`; check export bundle version branch |

## v1.x reproduction (unchanged)

paper-v1.0 / v1.2.0 reproductions continue to use existing quickstart in `specs/012-research-repro-kit/quickstart.md`.
