# Feature Specification: Research Reproduction Kit (Graph-Grounded Agentic Retrieval)

**Feature Branch**: `012-research-repro-kit`

**Created**: 2026-05-30

**Status**: Draft

**Input**: User description: "Build feature 012: a research reproduction kit for the paper 'Graph-Grounded Agentic Retrieval' centered on the published custom-judge evaluation dataset only (do not use upstream FinDER, FinanceBench, or FinAgentBench adapters for headline comparisons). The kit must provide scripted end-to-end workflows to (1) rebuild frozen corpora from a tagged release manifest, (2) run benchmark evaluation on a chosen custom-judge version and split offline with zero live EDGAR, (3) execute paired system variants on identical items—graph-full production agent, flat-chunk RAG baseline without graph navigation, and configurable ablations (e.g. no macro router, no graph walker, XBRL-only)—and (4) export aggregate paper tables with overall and by-inspiration-profile strata breakdowns (financebench, finder, finagentbench task families, cited only as taxonomy inspiration not as external benchmark runs). Metrics: outcome accuracy, rubric alignment, MRR/MAP/nDCG@10, graph-structural scores (accession binding accuracy, expected section path hit rate, multi-filing success rate), and trajectory fidelity; exclude incomplete trajectories from headline aggregates per feature 010. Dataset enhancement (required for published custom-judge v1.0+ used by this kit): at publish time (or a documented post-publish materialize step before eval), derive and persist relevant_chunk_ids for each accepted item by resolving all graph chunk nodes under each expected_section_path in the bundled graph snapshot (deterministic, content-addressed, recorded in manifest); at least 90% of published items must have non-empty relevant_chunk_ids so ranking metrics are graph-grounded on the native corpus. Non-goals: production UI and multi-tenant hosting. Success: a new researcher at release tag paper-v1.0 reproduces headline and by-profile tables within documented time and compute bounds using only README and pinned configuration (git SHA, custom-judge version, corpus/LFS hashes, judge and LLM pins); paired comparisons show graph-full improvements over flat-chunk baseline on the same custom-judge items. Depends on features 001, 004, 010, and 011."

## Clarifications

### Session 2026-05-30

- Q: Which benchmark corpora are in scope for headline paper tables? → A: **custom-judge only** — published versioned bundles from feature 011; upstream FinDER / FinanceBench / FinAgentBench adapters are **out of scope** for headline comparisons (chunk-oriented external sets do not exercise graph-grounded retrieval fairly).
- Q: How are public benchmark names used? → A: **Taxonomy inspiration only** — `inspiration_profile` strata (`financebench`, `finder`, `finagentbench`) label task families within custom-judge; they are not separate evaluation datasets in this kit.
- Q: When are graph-derived relevance labels materialized? → A: **At or before first eval** — as part of custom-judge publish (preferred) or a documented post-publish materialize step that must complete before reproduction runs; results are deterministic and recorded in the dataset manifest.
- Q: For release tag `paper-v1.0`, how should headline tables be reproduced? → A: **Live re-execution** — full agent + judge re-run with pinned model configs; graph-structural and ranking metrics (on frozen relevance labels) MUST match exactly; outcome accuracy, rubric alignment, and trajectory fidelity MAY vary within documented tolerance bands when live judge/LLM are used.
- Q: Which variants are required in the `paper-v1.0` release manifest? → A: **Full ablation suite** — graph-full, flat-chunk, and all three ablations (no macro router, no graph walker, XBRL-only); five variant runs minimum for `paper-v1.0` headline reproduction.
- Q: How should the flat-chunk RAG baseline retrieve chunks? → A: **Dense embedding retrieval** — embed query and frozen corpus chunks with a pinned embedding model; rank by cosine similarity and take top-k (no graph navigation).
- Q: Which graph node types are included in `relevant_chunk_ids` materialization? → A: **All evidence chunk types** — `CHUNK_PARAGRAPH`, `CHUNK_XBRL_FACT`, `CHUNK_TABLE`, and `CHUNK_ROW` reachable under each `expected_section_path` via structural containment.
- Q: Which custom-judge split should `paper-v1.0` headline reproduction evaluate? → A: **Full published `dev` split** — headline tables on all items in `items/dev.jsonl` for the pinned custom-judge version.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproduce Paper Tables from a Tagged Release (Priority: P1)

A researcher checking out release tag `paper-v1.0` follows README instructions only—no ad-hoc scripts—to rebuild the frozen evaluation environment, run all configured system variants on the pinned custom-judge version, and obtain aggregate tables matching the paper's headline results within documented tolerance.

**Why this priority**: The paper's credibility depends on third-party reproducibility without author assistance.

**Independent Test**: A new machine with repository checkout at `paper-v1.0`, LFS corpus pulled, and documented environment variables reproduces `tables/headline.csv` and `tables/by_profile.csv` matching the release manifest's recorded aggregate hashes within tolerance.

**Acceptance Scenarios**:

1. **Given** release manifest at `paper-v1.0` listing git SHA, custom-judge version, eval split (`dev`), corpus content hashes, judge pins, and variant list, **When** the researcher runs the documented reproduction workflow, **Then** all headline tables are produced under a deterministic output directory without live EDGAR access.
2. **Given** two researchers run the workflow on the same tag and pins with live re-execution, **When** both complete successfully, **Then** graph-structural and ranking metrics match exactly; outcome, rubric, and trajectory-fidelity aggregates match within documented tolerance bands recorded in the release manifest.
3. **Given** a missing LFS object or corpus hash mismatch, **When** rebuild runs, **Then** the workflow fails fast with an explicit artifact list—not silent partial results.

---

### User Story 2 - Graph-Grounded Relevance Labels on Published Items (Priority: P1)

A release engineer publishes (or post-processes) custom-judge v1.0+ so every evaluable item carries **relevant_chunk_ids** derived from the bundled graph under each item's `expected_section_path`, enabling ranking metrics that are native to the SEC/XBRL graph corpus.

**Why this priority**: MRR/MAP/nDCG comparisons between graph-full and flat-chunk baselines require graph-grounded relevance judgments on the same items—not external chunk labels.

**Independent Test**: After materialize-relevance on a published bundle, ≥90% of items have non-empty `relevant_chunk_ids`; re-running the step yields identical relevance label hash recorded in manifest.

**Acceptance Scenarios**:

1. **Given** an accepted item with one or more `expected_section_paths` resolvable in the bundled graph index, **When** relevance materialization runs, **Then** `relevant_chunk_ids` lists all evidence chunk nodes (`CHUNK_PARAGRAPH`, `CHUNK_XBRL_FACT`, `CHUNK_TABLE`, `CHUNK_ROW`) under those section paths via structural containment (deterministic ordering, stable node identifiers).
2. **Given** a published custom-judge version used by release `paper-v1.0`, **When** an operator inspects the dataset manifest, **Then** it records `relevance_labels_hash`, fraction of items with non-empty chunk labels, and graph snapshot id used for derivation.
3. **Given** relevance materialization completes, **When** fewer than 90% of items have non-empty labels, **Then** publish/repro gate fails with a report listing items that could not be labeled and why.

---

### User Story 3 - Paired System Variant Evaluation on Identical Items (Priority: P2)

An evaluation engineer runs **graph-full** (production agent), **flat-chunk RAG** (same frozen corpus, no graph navigation), and **all three ablations** (no macro router, no graph walker, XBRL-only) on the **same** custom-judge item set so the paper can claim graph-grounded improvements and component-level ablation results fairly.

**Why this priority**: Headline claims require controlled comparisons on identical questions, bindings, and corpus—not cross-dataset mixes.

**Independent Test**: Run two variants on custom-judge dev split (≥20 items smoke); verify per-item results share item ids and output `tables/variant_delta.csv` showing graph-full minus flat-chunk per metric.

**Acceptance Scenarios**:

1. **Given** variant configuration declaring graph-full and flat-chunk baselines, **When** benchmark evaluation runs offline on custom-judge v1.0 dev split, **Then** each item produces scores for outcome accuracy, rubric alignment (where applicable), ranking metrics (where chunk labels exist), graph-structural scores, and trajectory fidelity.
2. **Given** a finagentbench-profile item requiring multiple filings, **When** graph-full runs, **Then** multi-filing success rate reflects whether both expected accessions were used; flat-chunk variant is scored on the same structural expectations where applicable.
3. **Given** a trajectory marked incomplete per feature 010, **When** aggregates are computed, **Then** that item is excluded from headline fidelity and accuracy tables but counted in a separate audit table.

---

### User Story 4 - Stratified Reporting by Inspiration Profile (Priority: P2)

A paper author exports tables broken down by custom-judge **inspiration_profile** strata (financebench / finder / finagentbench task families) to show where graph-grounded retrieval helps most (e.g., multi-filing agentic items vs single-filing numeric QA).

**Why this priority**: Aggregate-only tables hide profile-specific strengths; the paper narrative requires task-family breakdown without running external benchmarks.

**Independent Test**: Export `tables/by_profile.csv` with one row per profile × variant; columns match headline metrics.

**Acceptance Scenarios**:

1. **Given** a completed multi-variant eval run, **When** export runs, **Then** `by_profile.csv` includes rows for each inspiration_profile with item counts and all headline metrics per variant.
2. **Given** finder-profile items with rubric-only ground truth, **When** scores are aggregated, **Then** rubric alignment is reported as the primary outcome column for that stratum (answer accuracy omitted or marked N/A).

---

### User Story 5 - Frozen Corpus Rebuild from Release Manifest (Priority: P3)

A researcher restores the exact evaluation corpus bundled with custom-judge—graph snapshots, parsed artifacts, and verification hashes—starting only from the release manifest and Git LFS, without re-fetching EDGAR.

**Why this priority**: Offline reproducibility (feature 011 SC-002) is prerequisite for fair variant comparisons.

**Independent Test**: `rebuild-corpus` on a clean checkout after `git lfs pull` yields manifest hash match and successful offline eval dry-run.

**Acceptance Scenarios**:

1. **Given** release manifest corpus hashes, **When** rebuild verifies bundled artifacts, **Then** every hash matches or the step fails with missing-object instructions.
2. **Given** `OFFLINE_BENCHMARK=1`, **When** evaluation runs after rebuild, **Then** zero network calls to EDGAR occur (verified by documented smoke procedure).

---

### Edge Cases

- Custom-judge version lacks relevance labels: reproduction workflow runs materialize-relevance first or fails with explicit gate message.
- Item has `expected_section_path` with zero resolvable chunk nodes: item excluded from ranking aggregates; counted in labeling failure report.
- Judge API unavailable during full reproduction: documented retry/degrade policy matches feature 010; degraded runs excluded from headline aggregates.
- Variant configuration requests unknown ablation id: fail at workflow start with valid variant list from release manifest.
- Published bundle has fewer than 200 items: reproduction allowed for smoke tags; headline tag `paper-v1.0` requires published custom-judge meeting 011 publish gate on the full `dev` split.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The kit MUST define a **release manifest** for tags such as `paper-v1.0` recording git SHA, custom-judge version, corpus and relevance label content hashes, judge model pins, LLM pins, **embedding model pin** (for flat-chunk baseline), and the ordered list of system variants to execute.
- **FR-002**: The kit MUST provide a documented **end-to-end reproduction workflow** (single entry command or fixed script chain) that rebuilds corpus artifacts, **re-executes** all manifest variants (live agent + judge with pinned configs), and exports paper tables without live EDGAR when `OFFLINE_BENCHMARK=1`.
- **FR-002a**: Release tag `paper-v1.0` reproduction MUST use **live re-execution** (not frozen per-item artifact replay); the release manifest MUST document tolerance bands for judge-stochastic metrics and require exact match for graph-structural and ranking metrics.
- **FR-002b**: Release tag `paper-v1.0` headline evaluation MUST use the **full published `dev` split** (`items/dev.jsonl`) for the pinned custom-judge version; subsamples and held-out test splits are out of scope for v1 headline tables.
- **FR-003**: Headline evaluation MUST use **custom-judge only**; upstream FinDER, FinanceBench, and FinAgentBench registry adapters MUST NOT be invoked for headline or by-profile tables in this feature.
- **FR-004**: The kit MUST support **paired system variants** on identical custom-judge items at minimum: **graph-full** (production graph-grounded agent) and **flat-chunk RAG** (same frozen corpus and chunks, no graph navigation).
- **FR-004a**: The **flat-chunk** variant MUST retrieve evidence via **dense embedding retrieval** only: embed the item query and all eligible frozen corpus chunks with a **pinned embedding model** recorded in the release manifest; rank by cosine similarity and select top-k chunks. BM25-only, hybrid, and oracle/metadata-guided retrieval are out of scope for the baseline.
- **FR-005**: The kit MUST support **configurable ablation variants** (declarative config, not retrieval code forks) including at least: no macro router, no graph walker, XBRL-only (no HTML narrative supplement)—selectable per release manifest.
- **FR-005a**: Release tag `paper-v1.0` MUST require **five variant runs** in the release manifest: **graph-full**, **flat-chunk**, and **all three** ablations listed in FR-005; partial ablation subsets are insufficient for headline reproduction.
- **FR-006**: For custom-judge **v1.0+** bundles used by reproduction releases, the system MUST **derive and persist `relevant_chunk_ids`** per item by resolving all evidence chunk nodes (`CHUNK_PARAGRAPH`, `CHUNK_XBRL_FACT`, `CHUNK_TABLE`, `CHUNK_ROW`) under each `expected_section_path` in the bundled snapshot via structural containment; derivation MUST be deterministic and content-addressed.
- **FR-007**: Relevance materialization MUST run at **publish time (preferred)** or via a **documented post-publish step** that is a mandatory gate before eval; the dataset manifest MUST record `relevance_labels_hash`, labeling coverage rate, and snapshot id.
- **FR-008**: Publish/repro gate MUST require **≥90%** of published items have non-empty `relevant_chunk_ids`; items below threshold MUST be listed in a labeling report.
- **FR-009**: Evaluation MUST compute and export **outcome accuracy** (where `ground_truth.answer` exists), **rubric alignment** (where `ground_truth.rubric` exists), **MRR, MAP, nDCG@10** (where `relevant_chunk_ids` exist), **graph-structural scores** (accession binding accuracy, expected section path hit rate, multi-filing success rate), and **trajectory fidelity**.
- **FR-010**: Headline aggregates MUST **exclude incomplete trajectories** per feature 010; incomplete and degraded judge runs MUST appear in a separate audit export with counts.
- **FR-011**: Export MUST produce **paper-ready tables**: overall headline (all manifest variants), by inspiration_profile stratum, variant delta (graph-full minus flat-chunk plus ablation deltas vs graph-full), and trajectory audit summary—in machine-readable (CSV) and human-readable (CSV and/or LaTeX) formats.
- **FR-012**: All evaluation runs MUST record custom-judge version, snapshot id, generation seed (if present), variant id, judge pins, and per-item trace identifiers for audit (feature 010 / 011 alignment).
- **FR-013**: Documentation MUST state **time and compute bounds** for full reproduction (e.g., hours, CPU/RAM, optional GPU for local LLM, LFS download size) so a new researcher can plan execution.
- **FR-014**: CI MUST include a **smoke reproduction** path (≤20 items, mock judge permitted) validating workflow wiring without full paper cost.

### Key Entities

- **ReleaseManifest**: Tag id, git SHA, custom-judge version, eval split (`dev` for `paper-v1.0`), corpus hashes, relevance label hash, variant list (for `paper-v1.0`: graph-full, flat-chunk, and all three FR-005 ablations), judge/LLM/**embedding** pins, expected table checksums.
- **SystemVariant**: Identifier (graph-full, flat-chunk, ablation-*), declarative capability flags, retrieval mode (flat-chunk: dense-embedding only), description for paper methods section.
- **RelevanceLabelSet**: Per-item mapping from item id to ordered `relevant_chunk_ids` (all four evidence chunk types under section paths); content hash; coverage statistics.
- **EvalRun**: Variant id, dataset version, split, item results, MLflow parent run id, exclusion counts.
- **PaperTableExport**: Headline aggregates, by-profile breakdown, variant deltas, audit counts; export timestamp and manifest reference.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new researcher at release tag `paper-v1.0` reproduces headline and by-profile tables on the **full published `dev` split** (covering all five required variants) using **only README and release manifest** within **documented time bounds** (target: ≤8 hours wall-clock with LFS pre-pulled on a documented reference machine running the full ablation suite).
- **SC-002**: On custom-judge v1.0+ dev split, **≥90%** of items have non-empty graph-derived `relevant_chunk_ids` after relevance materialization; labeling is **bitwise reproducible** (same hash on re-run).
- **SC-003**: Paired comparison on the same items shows **graph-full** exceeds **flat-chunk** on at least two of: mean outcome accuracy, mean nDCG@10, mean section path hit rate—with per-profile breakdown documented in exported tables.
- **SC-004**: Re-running the full live reproduction workflow at the same tag yields graph-structural and ranking metrics matching release manifest checksums **exactly**; outcome, rubric, and trajectory-fidelity aggregates match within **documented tolerance bands** pinned in the release manifest.
- **SC-005**: Offline reproduction completes with **zero live EDGAR fetches** when offline mode is enabled; violation is a hard failure in smoke verification.
- **SC-006**: Headline aggregates exclude **100%** of incomplete trajectories; audit export reports their count separately.
- **SC-007**: CI smoke reproduction (≤20 items) completes in **≤15 minutes** on standard CI runners with mock judge.

## Assumptions

- **Primary eval corpus**: Published **custom-judge** v1.0+ (≥200 items per 011 publish gate) is available at the release tag, with bundled corpus via Git LFS.
- **Profile strata**: `financebench`, `finder`, and `finagentbench` inspiration profiles denote **task families within custom-judge**, not external benchmark runs; paper citations to [FinanceBench](https://arxiv.org/abs/2311.11944), [FinDER](https://arxiv.org/abs/2504.15800), and [FinAgentBench](https://arxiv.org/abs/2508.14052) are **taxonomy attribution only**.
- **Dependencies**: Features **001** (registry/metrics), **004** (materialization/graph), **010** (trajectories, judge, validation gates), **011** (custom-judge bundles, offline eval) are implemented on the branch baseline.
- **Flat-chunk baseline**: Uses the same frozen chunk inventory extracted from the bundled graph corpus; retrieves via **dense embedding similarity** (pinned model in release manifest) with graph navigation and agentic routing disabled—fair comparison for graph claims.
- **Reproduction mode (`paper-v1.0`)**: **Live re-execution** with pinned agent LLM and judge configs; no frozen artifact replay for headline tables. CI smoke uses mock judge/LLM with the same exclusion rules.
- **Metric reproducibility**: Structural and ranking metrics are deterministic given frozen corpus and relevance labels; judge/outcome metrics tolerate documented variance across live re-runs.
- **Non-goals**: Production web UI, multi-tenant hosting, headline tables on upstream chunk-only benchmark adapters.

## Out of Scope

- Running or reporting FinDER, FinanceBench, or FinAgentBench adapter suites as headline comparisons.
- Hosting datasets or evaluation results outside repository release artifacts.
- Interactive visualization dashboards (exported CSV/LaTeX suffice).
- Training or fine-tuning retrieval models.
