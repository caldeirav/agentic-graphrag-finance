# Evaluation Dataset Quality Workflow (018)

**Feature branch:** `018-eval-dataset-quality`  
**Spec:** [specs/018-eval-dataset-quality/spec.md](../specs/018-eval-dataset-quality/spec.md)  
**Quickstart:** [specs/018-eval-dataset-quality/quickstart.md](../specs/018-eval-dataset-quality/quickstart.md)

This document summarizes what was implemented, how to fix generation issues at scale (not item-by-item), and the simplified CSV annotation workflow.

---

## Problem statement

Reproduction on `paper-v1.0` / `v2.0.0` showed **84 tier-1 items**: high retrieval (MRR ≥ 0.5 or nDCG@10 ≥ 0.3) but **zero outcome score**. A major root cause is **boilerplate comparison canonical answers** — e.g. “Both X and Y discuss topic Z in Item 1A” without a compared conclusion.

v2.0.0 was generated **before** the boilerplate publish gate existed. Fixing all 84 items via one-off CLI annotations is the wrong default; use **generation fixes + bulk regenerate** first, then CSV review for exceptions.

---

## What was implemented (changelog)

### Review package (`src/evaluation/generation/review/`)

| Module | Purpose |
|--------|---------|
| `queue.py` | Repro-driven review queue (tier 1/2/3) |
| `annotations.py` | Append-only `annotations.jsonl` |
| `overrides.py` | Apply human patches → `items/dev.jsonl` |
| `review_pack.py` | HTML + CSV audit pack |
| `quality_summary.py` | `quality_pass_summary.json` |
| `diversity.py` | `duplicate_feedback.jsonl`, `diversity_report.json` |
| `regenerate_item.py` | Per-item Gemini regen (preserves `item_id`) |
| `csv_annotations.py` | **Annotatable CSV export + import** |
| `bulk_regenerate.py` | **Bulk boilerplate fix via Gemini** |

### Generation improvements (prevent recurrence)

| Change | Location |
|--------|----------|
| `is_boilerplate_comparison_answer()` gate | `comparison_gt.py` |
| Publish gate: `boilerplate_comparison_count == 0` | `bundle.py` |
| Finagentbench prompt requires **compared conclusion** | `finagentbench.yaml` |
| Gemini v2 prompt rules (no co-occurrence-only answers) | `gemini_item_generator.py` |
| Duplicate feedback + issuer cap + negative examples | `judge_generator.py`, `custom_judge_v2.yaml` |
| Diversity governance config | `custom_judge_v2_quality.yaml` |

### CLI commands (`benchmark-dataset review …`)

| Command | Purpose |
|---------|---------|
| `export-queue` | Prioritized worklist from repro |
| `export-sheet` | **Annotatable CSV** (context + empty reviewer columns) |
| `import-csv` | **Import filled CSV** → `annotations.jsonl` [+ `--apply`] |
| `export-pack` | HTML + CSV for spot-check |
| `annotate` | Single-item annotation (legacy) |
| `apply-overrides` | Merge approved annotations into dev split |
| `fix-boilerplate` | **Bulk Gemini regen** for boilerplate comparisons |
| `regenerate-items` | Bulk regen for explicit item-id list |
| `summary` | Quality pass metrics |
| `extend-quality` | Extend v2.0.0 draft with sidecars |

### Release artifacts

- `releases/paper-v1.1/manifest.yaml` (parent: paper-v1.0, bundle: v2.0.1)
- `specs/018-eval-dataset-quality/checklists/quality-pass.md`

### Tests

32+ unit/integration tests under `tests/unit/test_review_*.py`, `test_csv_annotations.py`, `tests/integration/test_quality_*.py`, `tests/contract/test_review_import_boundary.py`.

---

## Recommended workflow for your 84 tier-1 items

### Step A — Bulk fix boilerplate at generation level (preferred)

Most finagentbench comparison items with co-occurrence-only answers should be **regenerated in place**, not hand-edited.

```bash
# 1. See how many tier-1 items are boilerplate comparisons
uv run agent-query benchmark-dataset review fix-boilerplate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --dry-run

# 2. Regenerate them (requires GOOGLE_API_KEY; start with a pilot batch)
uv run agent-query benchmark-dataset review fix-boilerplate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --max-items 20

# 3. Verify scorability
uv run python -c "
import json
from pathlib import Path
r = json.loads(Path('data/benchmarks/custom-judge/drafts/quality-v2.0.1/scorability_report.json').read_text())
print('boilerplate_comparison_count', r.get('boilerplate_comparison_count'))
"
```

`fix-boilerplate` calls Gemini with explicit feedback requiring a **compared conclusion** (whereas / emphasizes / differs). Results are written to `items/dev.jsonl` and logged in `override_changelog.jsonl` + `bulk_regenerate_report.json`.

Repeat `--max-items` batches until `boilerplate_comparison_count == 0`.

### Step B — CSV annotation for exceptions only

Use CSV for items that need **human judgment** (GT too strict, wrong bindings, ambiguous questions) — not for systematic boilerplate.

```bash
# 1. Export annotatable sheet for tier-1 queue
uv run agent-query benchmark-dataset review export-sheet \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --repro-input reports/repro-paper-v1.0 \
  --output annotation_sheet_tier1.csv

# 2. Open in Excel/Sheets; fill reviewer columns (see below)

# 3. Import + apply in one step
uv run agent-query benchmark-dataset review import-csv \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --csv annotation_sheet_tier1_filled.csv \
  --reviewer-id "${USER}" \
  --apply
```

#### CSV columns you fill in

| Column | Values | Required for apply |
|--------|--------|-------------------|
| `failure_class` | `gt_boilerplate`, `gt_too_strict`, `gt_wrong`, `question_ambiguous`, `claims_misaligned`, `acceptable_hard`, `agent_failure` | yes |
| `corpus_spot_check` | `passed` (or `yes`) | yes |
| `notes` | Free text | no |
| `proposed_answer` | New canonical answer | one of answer/question |
| `proposed_question` | New question text | one of answer/question |
| `apply` | `yes` / `no` (blank = import if other fields valid) | `no` skips import |

Context columns (`question`, `canonical_answer`, `is_boilerplate_comparison`, repro scores) are export-only.

**Dry-run import:**

```bash
uv run agent-query benchmark-dataset review import-csv \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --csv annotation_sheet_tier1_filled.csv \
  --reviewer-id "${USER}" \
  --dry-run
```

### Step C — Validate fixes (selective re-judge)

```bash
uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variant graph-full \
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue_tier1_ids.json \
  --force-rescore

uv run agent-query benchmark-dataset review summary \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0
```

### Step D — Publish v2.0.1

When `boilerplate_comparison_count == 0` and other v2 gates pass:

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --version 2.0.1 \
  --publish-signoff \
  --operator-id "${USER}"
```

---

## Generation vs annotation: when to use which

| Situation | Use |
|-----------|-----|
| Boilerplate comparison answer (systematic) | `review fix-boilerplate` |
| GT wording tweak, numeric fix, question edit | CSV `import-csv` |
| Item needs full re-authoring | `regenerate-item` or `review regenerate-items` |
| Agent failed but GT is correct | Annotate `agent_failure`; do **not** apply override |
| Future net-new generation | `custom_judge_v2_quality.yaml` + updated prompts; gate blocks publish |

---

## Immutability constraints

- `data/benchmarks/custom-judge/v2.0.0/` — **never modify**
- `releases/paper-v1.0/` — **never modify**
- Quality work happens in `drafts/quality-v2.0.1` → publish `v2.0.1` → `paper-v1.1`

---

## Related docs

- [custom-judge-dataset-generation.md](custom-judge-dataset-generation.md) — generation pipeline + quality pass summary
- [research-reproduction.md](research-reproduction.md) — full repro after publish
- [018 contracts](../specs/018-eval-dataset-quality/contracts/) — CLI and gate contracts
