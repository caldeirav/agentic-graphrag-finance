# Quality Pass Operator Checklist (018)

**Feature**: 018-eval-dataset-quality · **Target**: `v2.0.1` + `paper-v1.1`

## Phase 1 — Setup

- [ ] Branch `018-eval-dataset-quality` rebased on `main`
- [ ] `data/benchmarks/custom-judge/v2.0.0/` present locally (immutable)
- [ ] `reports/repro-paper-v1.0/` baseline present locally
- [ ] `extend-quality` draft created at `data/benchmarks/custom-judge/drafts/quality-v2.0.1`

## Phase 2 — Triage

- [ ] `review export-queue` run against repro-paper-v1.0
- [ ] Tier-1 count recorded (target: identify dataset-likely zero-outcome items)
- [ ] `review export-pack` generated for tier-1 subset (HTML + CSV)

## Phase 3 — Human review

- [ ] 20-item structural spot-check completed from review pack
- [ ] Annotations appended to `annotations.jsonl` with failure class + corpus spot-check
- [ ] `agent_failure` items excluded from override apply unless `--force`

## Phase 4 — Apply fixes

- [ ] `review apply-overrides` dry-run passes v2 gates
- [ ] `override_changelog.jsonl` records parent item hashes
- [ ] `scorability_report.json` shows `boilerplate_comparison_count == 0`

## Phase 5 — Validate improvements

- [ ] Selective `repro judge-batch` with `--bundle-override` on fixed item ids
- [ ] `review summary` shows improved `rejudge_improved_rate`
- [ ] `quality_pass_summary.json` archived in draft

## Phase 6 — Publish

- [ ] `publish --version 2.0.1 --publish-signoff` succeeds
- [ ] `releases/paper-v1.1/manifest.yaml` updated with new `items_hash`
- [ ] `data/benchmarks/custom-judge/v2.0.0/` unchanged (`git diff` empty)

## Phase 7 — Full repro (optional)

- [ ] `repro run-all --manifest releases/paper-v1.1/manifest.yaml`
- [ ] `expected_checksums.json` recorded for paper-v1.1 baseline

## Notes

| Run date | Tier-1 count | Items fixed | Rejudge improved rate |
|----------|--------------|-------------|------------------------|
|          |              |             |                        |
