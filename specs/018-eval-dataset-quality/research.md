# Research: Evaluation Dataset Quality Improvement (018)

**Feature**: 018-eval-dataset-quality | **Date**: 2026-06-20

## R1 — Quality-pass delivery model

**Decision**: **In-place patch** on the existing 200 dev items from v2.0.0 parent via `benchmark-dataset extend --parent-version 2.0.0`; overrides and per-slot regeneration preserve `item_id` where possible; publish as **v2.0.1**. No dev_pool re-selection.

**Rationale**: Clarification session 2026-06-20; minimizes paper comparison drift and matches surgical HITL workflow.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| dev_pool re-selection | Swaps item identities; breaks item-for-item repro comparison |
| Net-new quality bundle (v2.1.0) | Unnecessary churn when corpus unchanged |

---

## R2 — Annotation artifact location

**Decision**: Append-only **`annotations.jsonl`** sidecar in draft bundle root; **`override_changelog.jsonl`** written on apply; dev items unchanged until `benchmark-dataset apply-overrides`.

**Rationale**: Co-located with draft for audit; separates review intent from canonical eval records (FR-002, FR-004).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| External `reviews/` tree | Orphan risk when draft moves or publishes |
| Embedded fields on dev rows | Pollutes items_hash on every note; loses append-only history |

---

## R3 — Review queue priority signal

**Decision**: Tier-1 (dataset-likelihood): `outcome_score == 0` AND (`mrr >= 0.5` OR `ndcg_at_10 >= 0.3`) on baseline variant `graph-full`. Tier-2: zero outcome with weaker retrieval. Tier-3: non-zero outcome with annotation-worthy anomalies. Export as `review_queue.json` + CSV.

**Rationale**: Clarification thresholds; aligns with v2.0.0 observation (~47% VA=0 on graph-full, many with MRR>0.5).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| MRR > 0 only | Too noisy; floods queue with binding failures |
| Manual sort only | Not reproducible across operators |

---

## R4 — Comparison boilerplate detection

**Decision**: Extend `comparison_gt.py` with **`is_boilerplate_comparison_answer(answer)`** rejecting answers that:
1. Match `_BOTH_FILINGS_PATTERN` (section co-occurrence), AND
2. Lack substantive comparison signal: no `_CROSS_VERB`, no entity-specific contrast phrase, and answer token count < 25 after removing boilerplate template tokens.

Add validation error `boilerplate_comparison_answer`. Human review flags borderline via annotation class `gt_boilerplate`.

**Rationale**: v2.0.0 finagentbench items pass `_BOTH_FILINGS_PATTERN` but canonical answer is non-informative; claims carry substance (FR-010).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| LLM classifier at validation | Extra API cost; non-deterministic gates |
| Human-only | Too many items (66 comparison) slip through publish |

---

## R5 — Duplicate feedback and diversity governance

**Decision**:
- Write **`duplicate_feedback.jsonl`** during judge phase (extend `judge_generator.py`) on each duplicate rejection: `{rejected_question, matched_item_id, profile, issuer_ticker, similarity_score}`.
- Add **`diversity_governance`** to generation config: `max_items_per_issuer_per_profile`, `min_unique_question_type_tags_per_profile`, `prompt_negative_examples_count` (prior accepted questions injected into Gemini prompt).
- Emit **`diversity_report.json`** per run with duplicate rejection rate, issuer histogram, question-type histogram vs v2.0.0 baseline.

**Rationale**: 283/700 duplicate rejections in v2.0.0; profile quota alone insufficient (FR-007, FR-008, SC-004).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Lower dedup threshold | Increases near-duplicate items in pool |
| Post-hoc dev_pool dedup only | Does not fix generation waste |

---

## R6 — Review pack format

**Decision**: **`review_pack.html`** + **`review_pack.csv`** under draft or operator output dir; HTML reuses 014 report styling (read-only, section excerpts from bundled corpus); CSV columns match annotation import schema.

**Rationale**: Clarification HTML+CSV; 30-minute audit target (SC-001).

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| CSV only | Poor corpus spot-check UX |
| MLflow dataset export | Not source of truth; extra infra |

---

## R7 — Selective re-judge after GT fixes

**Decision**: Extend `repro judge-batch` with `--item-ids-file` and `--bundle-override PATH` (draft or published bundle for updated GT). Judge loads items from override bundle by `item_id` while answers/trajectories come from existing `results.json`. Emit **`quality_pass_summary.json`** comparing pre/post VA on fixed item set.

**Rationale**: SC-003 without 8h full repro; 015 re-judge workflow already exists; `run-all` already supports `--item-ids-file`.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Full repro per fix iteration | Operator cost prohibitive |
| Mock judge for GT validation | Does not validate real judge alignment |

---

## R8 — paper-v1.1 release lock

**Decision**: New **`releases/paper-v1.1/manifest.yaml`** pointing at `custom_judge_version: 2.0.1`, same corpus hashes as v2.0.0 (in-place patch), new `items_hash`, refreshed `expected_checksums.json` after full repro on v2.0.1. paper-v1.0 immutable.

**Rationale**: Clarification session; matches 017 release lineage pattern.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Update paper-v1.0 in place | Breaks frozen baseline audit |
| Bundle-only publish without paper lock | No reproducible headline comparison |

---

## R9 — Targeted item regeneration

**Decision**: New CLI `benchmark-dataset regenerate-item --draft PATH --item-id ID` calling `GeminiItemGenerator.generate_one` with merged constraints: prior validation errors, annotation notes, diversity negative examples, and **same item_id slot** (in-place content replace).

**Rationale**: FR-009; reuses existing `validation_feedback` retry path in `judge_generator.py`.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| Re-run full judge phase | Regenerates all 220 candidates |
| Manual JSON edit only | No validation feedback loop for hard items |

---

## R10 — MLflow for re-judge (optional)

**Decision**: Log selective re-judge runs to MLflow as **secondary** artifacts (`quality_rejudge_summary.json` per parent run); bundle `items_hash` remains canonical eval lock (FR-017).

**Rationale**: Constitution III alignment without dual source of truth.

**Alternatives considered**:
| Alternative | Rejected because |
|-------------|------------------|
| MLflow Evaluation Datasets as primary store | SQL server requirement; duplicates JSONL bundle |
