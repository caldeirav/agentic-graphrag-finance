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

Resume judge only (checkpoint revalidation + dev split rebuild):

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-20260602 \
  --bundle-version 2.0.0 \
  --phase judge
```

Review outputs under `data/benchmarks/custom-judge/drafts/v2-draft-20260602/`:

| Report / artifact | Acceptance |
|-------------------|------------|
| `generation_report.json` | `pool_accepted` ≥ 200 in pool; `pass_rate` is **indicative only** (candidate yield) |
| `items/dev_pool.jsonl` | All unique accepted items (may exceed 200) |
| `items/dev.jsonl` | **200** quota-balanced rows; manifest `item_count` must match |
| `dev_selection_report.json` | `selected_counts` match `targets` (e.g. 68 / 66 / 66) |
| `manifest.json` `profile_counts` | Matches `dev_selection_report.selected_counts` |
| `feasibility_report.json` | `blocked_count: 0`, `macro_bindability_failures: 0` |
| `scorability_report.json` | `answer_gt_coverage: 1.0`, `rubric_only_count: 0` |
| `multi_filing_count` | ≥ 40 (publish gate) |

Console **Generate complete** panel shows `dev_selected` and `dev_profile_counts`, not just pool totals.

## Phase 2 — Operator audit (10%)

1. Open `publish_audit.sample.json` — 20 stratified item ids.
2. For each item verify: question clarity, answer-GT correctness, claims atomicity (per-filing + cross-filing synthesis for comparison items), bindings feasible.
3. Record notes; fix blocked items in draft or regenerate backfill if needed.

## Phase 3 — Publish v2.0.0

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/v2-draft-20260602 \
  --version 2.0.0 \
  --publish-signoff \
  --operator-id "${USER}"
```

Publish re-runs profile-balanced selection from `dev_pool.jsonl`, then applies v2 quality gates. **Not blocking**: `generation_report.pass_rate`.

Verify:
- `data/benchmarks/custom-judge/v2.0.0/manifest.json` → `version: "2.0.0"`, `schema_version: "2.0.0"`
- `profile_counts` balanced (~34% / 33% / 33%)
- `dev_selection_report.json` on published bundle
- v1.2.0 directory unchanged: `git diff data/benchmarks/custom-judge/v1.2.0`

## Phase 4 — paper-v2.0 release lock

```bash
uv run agent-query repro materialize-relevance \
  --manifest releases/paper-v2.0/manifest.yaml
```

Commit `releases/paper-v2.0/manifest.yaml` with pinned `items_hash`, `corpus_hashes`, `relevance_labels_hash` from published `v2.0.0` manifest.

## Phase 5 — Full reproduction (five variants × 200 items)

```bash
export OFFLINE_BENCHMARK=1 USE_MOCK_LLM=0 USE_MOCK_JUDGE=0

git lfs pull --include="data/benchmarks/custom-judge/v2.0.0/corpus/**"

# Lock repro (requires REPRO_ALLOW_FULL=1 during agent iteration freeze)
export REPRO_ALLOW_FULL=1
uv run agent-query repro run-all \
  --manifest releases/paper-v2.0/manifest.yaml \
  --output reports/repro-paper-v2.0-lock \
  --defer-judge --no-resume

uv run agent-query repro verify-tables \
  --manifest releases/paper-v2.0/manifest.yaml \
  --input reports/repro-paper-v2.0-lock

uv run agent-query repro report \
  --input reports/repro-paper-v2.0-lock \
  --manifest releases/paper-v2.0/manifest.yaml
```

**No selective skip**: every item runs on every variant.

For day-to-day agent work, use `repro smoke-run` + `repro smoke-gate` instead — see [research-reproduction.md § Agent iteration](../../docs/research-reproduction.md#agent-iteration-smoke-gate-frozen-full-repro).

## Phase 6 — Verify unified task_success

Inspect `reports/repro-paper-v2.0-lock/tables/headline.csv`:

| Check | Expected |
|-------|----------|
| `task_success` item_count | 200 |
| `task_success` value | mean value_alignment (baseline ≈ 0.467 on lock repro) |
| `rubric_alignment` row | absent |
| MRR / nDCG@10 | present; definitions unchanged |
| `verify-tables` | passes against `releases/paper-v2.0/expected_checksums.json` |

Open `report.html` — headline section shows task_success as sole outcome metric; item drill-down groups by item with all variants adjacent.

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
| `multi_filing_floor` gate fails | Ensure finagentbench items accept into `dev_pool`; resume `--phase judge` after comparison-claims fixes |
| `macro_bindability` failures | Fix bindings or drop item; verify corpus has comparison partners |
| `ProfileSelectionError` (profile short) | Pool lacks enough accepts for one profile; generate more or adjust quotas |
| Unbalanced `dev.jsonl` | Confirm `dev_pool.jsonl` exists; re-run `--phase judge` or publish (re-selects) |
| `pass_rate` publish failure on v2 | Upgrade CLI; v2 must not gate on candidate pass_rate (check `schema_version: 2.0.0`) |
| task_success n < 200 | Check headline eligibility; v2 items must all have answer GT |
| rubric_alignment in v2 report | Verify release manifest pins `2.0.0`; check export bundle version branch |

## v1.x reproduction (unchanged)

paper-v1.0 / v1.2.0 reproductions continue to use existing quickstart in `specs/012-research-repro-kit/quickstart.md`.
