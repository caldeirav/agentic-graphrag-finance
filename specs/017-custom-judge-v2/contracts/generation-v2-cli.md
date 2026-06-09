# Contract: v2.0 Dataset Generation CLI (017)

**Extends**: `specs/011-judge-eval-dataset/contracts/dataset-generation-cli.md`

## Config

**Path**: `configs/benchmarks/custom_judge_v2.yaml`

| Field | v2.0 value | Notes |
|-------|------------|-------|
| `config_id` | `custom_judge_v2` | Distinct from v1 |
| `random_seed` | `20260602` (or documented) | Must differ from v1 seed 42 |
| `filing_filters.min_fiscal_year` | `2023` | Refreshed window |
| `filing_filters.max_fiscal_year` | `2026` | Includes latest quarters |
| `governance.max_items` | `240` | Headroom above 200 gate |
| `governance.multi_filing_min` | `40` | New v2 gate |
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
3. Generate net-new items (no v1.2.0 import)
4. Validate v2 gates including macro-bindability
5. Write `feasibility_report.json`, `scorability_report.json`
6. Emit stratified 20-item audit list in draft

Exit non-zero if `blocked_count > 0` or `multi_filing_count < 40`.

## Publish (requires audit sign-off)

```bash
# After manual review of 20 stratified items:
uv run agent-query benchmark-dataset publish \
  --draft-run-id v2-draft-20260602 \
  --version 2.0.0 \
  --publish-signoff \
  --operator-id "${USER}"
```

Writes `publish_audit.json` and promotes to `data/benchmarks/custom-judge/v2.0.0/`.

Publish blocked unless:
- All gates in `bundle-v2.0.md` pass
- `--publish-signoff` provided
- Audit sample item ids confirmed (interactive or `--audit-confirmed`)

## Materialize relevance labels

```bash
uv run agent-query repro materialize-relevance \
  --release paper-v2.0 \
  --bundle data/benchmarks/custom-judge/v2.0.0
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
├── manifest.json              # status: draft, schema 2.0.0
├── items/dev.jsonl
├── feasibility_report.json
├── scorability_report.json
├── reachability_report.json
├── publish_audit.sample.json  # 20-item stratified list (pre-signoff)
├── generation_report.json
├── sampling_manifest.json
└── corpus/
```
