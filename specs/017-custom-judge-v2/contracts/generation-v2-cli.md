# Contract: v2.0 Dataset Generation CLI (017)

**Extends**: `specs/011-judge-eval-dataset/contracts/dataset-generation-cli.md`

## Config

**Path**: `configs/benchmarks/custom_judge_v2.yaml`

| Field | v2.0 value | Notes |
|-------|------------|-------|
| `config_id` | `custom_judge_v2` | Distinct from v1 |
| `random_seed` | `20260602` (or documented) | Must differ from v1 seed 42; also selection seed |
| `filing_filters.min_fiscal_year` | `2023` | Refreshed window |
| `filing_filters.max_fiscal_year` | `2026` | Includes latest quarters |
| `profile_quotas` | `0.34 / 0.33 / 0.33` | Schedules generation; final dev split quota-balanced |
| `governance.max_items` | `240` | Headroom above 200 gate |
| `governance.multi_filing_min` | `40` | Publish gate on `dev.jsonl` |
| `governance.validation_pass_rate` | `0.95` | **Indicative** for v2 (not publish-blocking) |
| `bundle_schema_version` | `2.0.0` | Enforces v2 item shape |

## Generate (net-new draft)

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-20260602 \
  --bundle-version 2.0.0
```

Phases:
1. Sample issuers (allowlist + seed)
2. Materialize refreshed corpus (Docling/XBRL/graph)
3. Generate net-new items (no v1.2.0 import); checkpoint `candidates.jsonl`
4. Validate v2 gates; `normalize_v2_item` on revalidate
5. Write `items/dev_pool.jsonl` (all unique accepts)
6. **Profile-balanced selection** → `items/dev.jsonl` (200 items)
7. Write `feasibility_report.json`, `scorability_report.json`, `dev_selection_report.json`
8. Emit stratified 20-item audit list in draft

Exit non-zero if `blocked_count > 0` or `multi_filing_count < 40` on **selected** `dev.jsonl`.

### Resume judge

```bash
uv run agent-query benchmark-dataset generate \
  --config configs/benchmarks/custom_judge_v2.yaml \
  --run-id v2-draft-20260602 \
  --bundle-version 2.0.0 \
  --phase judge
```

Revalidates `candidates.jsonl`, rebuilds `dev_pool.jsonl` and quota-balanced `dev.jsonl`.

## Publish (requires audit sign-off)

```bash
uv run agent-query benchmark-dataset publish \
  data/benchmarks/custom-judge/drafts/v2-draft-20260602 \
  --version 2.0.0 \
  --publish-signoff \
  --operator-id "${USER}"
```

1. Copies draft → `data/benchmarks/custom-judge/v2.0.0/`
2. Re-runs profile-balanced selection from `dev_pool.jsonl` when pool > 200
3. Applies publish gates in `bundle-v2.0.md`
4. Writes `publish_audit.json` with operator sign-off

Publish blocked unless:
- All gates in `bundle-v2.0.md` pass on final `dev.jsonl`
- `--publish-signoff` provided
- `publish_audit.json` present

**Not blocking for v2**: `generation_report.pass_rate`.

## Materialize relevance labels

```bash
uv run agent-query repro materialize-relevance \
  --manifest releases/paper-v2.0/manifest.yaml
```

Updates `relevance_labels.json` and hash in bundle manifest.

## Forbidden flags

| Flag | Reason |
|------|--------|
| `--migrate-from 1.2.0` | FR-006 forbids migration path |
| `--reuse-item-ids` | Net-new pool |
| `--skip-macro-gate` | Blocking gate for all items |

## Output layout (draft)

```text
data/benchmarks/custom-judge/drafts/v2-draft-20260602/
├── manifest.json                 # status: draft, schema 2.0.0, profile_counts
├── generation_config.yaml
├── items/
│   ├── dev_pool.jsonl            # all unique accepted (pool)
│   └── dev.jsonl                 # 200 quota-balanced publish set
├── dev_selection_report.json     # pool_count, targets, selected_counts, seed
├── feasibility_report.json
├── scorability_report.json
├── reachability_report.json
├── publish_audit.sample.json     # 20-item stratified list (pre-signoff)
├── generation_report.json        # candidate yield (indicative for v2)
├── candidates.jsonl              # all attempts (checkpoint)
├── sampling_manifest.json
└── corpus/
```
