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

## Your next steps (after fix-boilerplate 27/27)

| Step | Action | Command |
|------|--------|---------|
| 1 | Confirm boilerplate queue empty | `review fix-boilerplate --dry-run` |
| 2 | Export tier-1 annotation sheet | `review export-sheet` |
| 3 | Review in Excel/Sheets (filter `is_boilerplate_comparison=no`) | — |
| 4 | Import patches | `review import-csv --apply` |
| 5 | Record agent failures (no GT edit) | `review annotate --failure-class agent_failure` |
| 6 | Optional spot-check | `review export-pack --max-items 20` |
| 7 | Re-judge fixed items | `repro judge-batch --bundle-override …` |
| 8 | Metrics | `review summary` |
| 9 | Publish | `publish --version 2.0.1 --publish-signoff` |

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

Repeat `--max-items` batches until `fix-boilerplate --dry-run` reports **0** remaining boilerplate comparisons in the tier-1 queue.

`fix-boilerplate` writes each accepted item to `items/dev.jsonl`, logs `override_changelog.jsonl`, and refreshes `scorability_report.json` when at least one item succeeds.

### Step A2 — After fix-boilerplate (27/27 succeeded)

You have fixed the boilerplate comparison subset. The remaining tier-1 work (~57 items) is **not** boilerplate — use review + CSV annotation below.

```bash
# Confirm no boilerplate comparisons remain in the tier-1 queue
uv run agent-query benchmark-dataset review fix-boilerplate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --dry-run

# Check scorability (boilerplate_comparison_count should drop)
uv run python -c "
import json
from pathlib import Path
p = Path('data/benchmarks/custom-judge/drafts/quality-v2.0.1/scorability_report.json')
print(json.loads(p.read_text()) if p.is_file() else 'run fix-boilerplate first')
"

# Optional: spot-check 10 regenerated items in the browser
uv run agent-query benchmark-dataset review export-pack \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --max-items 10 \
  --repro-input reports/repro-paper-v1.0 \
  --output-dir data/benchmarks/custom-judge/drafts/quality-v2.0.1/review/spot_check_regen
# Open review/spot_check_regen/review_pack.html — verify answers have compared conclusions
```

Regenerated items are already in `items/dev.jsonl` (no `apply-overrides` step needed for fix-boilerplate).

### Step B — CSV annotation for remaining tier-1 items

Use CSV for items that need **human judgment** (GT too strict, wrong bindings, ambiguous questions) — not for systematic boilerplate.

```bash
# 1. Export annotatable sheet for tier-1 queue (omit fix-boilerplate items)
uv run agent-query benchmark-dataset review export-sheet \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --repro-input reports/repro-paper-v1.0 \
  --exclude-regenerated \
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

**Tip:** After fix-boilerplate, use `--exclude-regenerated` to export only items not yet fixed by bulk regen (~57 rows). Re-running `export-sheet` **overwrites** the output CSV — copy a filled sheet before re-exporting.

**Tip:** Sort or filter on `is_boilerplate_comparison=no` if exporting all 84 tier-1 rows.

#### Worked examples (CSV rows)

Export columns are wide; below are the **reviewer columns only** with example values.

**Example 1 — GT too strict (numeric tolerance):** tighten canonical answer wording.

| item_id | failure_class | corpus_spot_check | notes | proposed_answer | apply |
|---------|---------------|-------------------|-------|-----------------|-------|
| v2-financebench-0042 | gt_too_strict | passed | Judge rejects 391.0B vs 391B; align to filing wording | $391 billion in net sales for fiscal 2024 | yes |

**Example 2 — Question ambiguous:** clarify scope so retrieval can succeed.

| item_id | failure_class | corpus_spot_check | notes | proposed_question | apply |
|---------|---------------|-------------------|-------|-------------------|-------|
| v2-finder-0018 | question_ambiguous | passed | "Recent filing" is ambiguous; anchor to FY2025 10-K | What cybersecurity risks does the company disclose in its FY2025 10-K Item 1A? | yes |

**Example 3 — Claims misaligned:** fix canonical answer; claims are re-derived on apply.

| item_id | failure_class | corpus_spot_check | notes | proposed_answer | apply |
|---------|---------------|-------------------|-------|-----------------|-------|
| v2-finagentbench-0122 | claims_misaligned | passed | Answer lacked cross-filing contrast | Both Caterpillar's 2025 10-K and Exxon Mobil's 2025 10-K emphasize supply-chain risk differently: Caterpillar highlights component availability whereas Exxon Mobil stresses logistics disruption in upstream operations. | yes |

**Example 4 — Acceptable hard (no dataset change):** record decision only; leave `apply` blank or `no`.

| item_id | failure_class | corpus_spot_check | notes | apply |
|---------|---------------|-------------------|-------|-------|
| v2-financebench-0091 | acceptable_hard | passed | Multi-step numeric derivation; GT is correct; agent should improve | no |

**Example 5 — Agent failure (GT correct):** use CLI `review annotate`, not CSV import — import requires `proposed_answer` or `proposed_question`.

```bash
uv run agent-query benchmark-dataset review annotate \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-id v2-finder-0033 \
  --failure-class agent_failure \
  --corpus-spot-check passed \
  --reviewer-id "${USER}" \
  --notes "Retrieval found correct section; synthesis omitted cited figure"
```

Do **not** run `apply-overrides` for `agent_failure` unless you intentionally patch GT with `--force`.

#### Import workflow

```bash
# Dry-run first (validates rows, no writes)
uv run agent-query benchmark-dataset review import-csv \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --csv annotation_sheet_tier1_filled.csv \
  --reviewer-id "${USER}" \
  --dry-run

# Import annotations + patch dev.jsonl in one step
uv run agent-query benchmark-dataset review import-csv \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --csv annotation_sheet_tier1_filled.csv \
  --reviewer-id "${USER}" \
  --apply
```

Rows are **skipped** when: `failure_class` empty, `corpus_spot_check` not `passed`, `apply=no`, or both `proposed_answer` and `proposed_question` empty.

### Step C — Spot-check review pack (optional, ~20 items)

Before large CSV edits, skim a structural sample in the browser:

```bash
uv run agent-query benchmark-dataset review export-pack \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --queue-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/review_queue.json \
  --max-items 20 \
  --repro-input reports/repro-paper-v1.0 \
  --output-dir data/benchmarks/custom-judge/drafts/quality-v2.0.1/review/pack_tier1
```

Open `review/pack_tier1/review_pack.html`. Check: question clarity, canonical answer vs corpus, section paths, repro scores.

### Step D — Validate fixes (selective re-judge)

```bash
# Build item-id list from fix-boilerplate + CSV overrides (accepted changelog entries)
uv run python -c "
import json
from pathlib import Path
root = Path('data/benchmarks/custom-judge/drafts/quality-v2.0.1')
ids = []
for line in (root / 'override_changelog.jsonl').read_text().splitlines():
    if not line.strip():
        continue
    row = json.loads(line)
    if row.get('validation_outcome') == 'accepted':
        ids.append(row['item_id'])
out = root / 'fixed_items.json'
out.write_text(json.dumps({'item_ids': sorted(set(ids))}, indent=2) + '\n')
print(f'Wrote {len(set(ids))} item ids -> {out}')
"

uv run agent-query repro judge-batch \
  --manifest releases/paper-v1.0/manifest.yaml \
  --input reports/repro-paper-v1.0 \
  --variant graph-full \
  --bundle-override data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --item-ids-file data/benchmarks/custom-judge/drafts/quality-v2.0.1/fixed_items.json \
  --force-rescore

uv run agent-query benchmark-dataset review summary \
  --draft data/benchmarks/custom-judge/drafts/quality-v2.0.1 \
  --repro-input reports/repro-paper-v1.0
```

Re-judge writes updated judge scores into the repro tree. Compare `quality_pass_summary.json` fields `rejudge_improved_rate` and `dataset_caused_zero_score_rate` before publish.

### Step E — Publish v2.0.1

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
