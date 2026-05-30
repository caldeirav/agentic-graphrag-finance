# Feature Specification: Judge-Generated Custom Evaluation Dataset

**Feature Branch**: `011-judge-eval-dataset`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "Specify construction of a custom evaluation dataset by the judge model: sample issuers and relevant filings, used to run the production Docling/XBRL ingestion pipeline, and produce JSONL benchmark items with questions, gold answers or rubrics, expected filing sets, expected section paths. For questions generation, leverage FinDER, FinAgentBench, or FinanceBench papers and datasets. Include governance for rate limits, storage budgets, and reproducible sampling seeds. Success: a versioned dataset of at least 200 items with documentation sufficient for third-party reproduction without live EDGAR access at evaluation time, with ability to reproduce and / or extend through CLI."

## Clarifications

### Session 2026-05-20

- Q: What is the issuer sampling universe for generation runs? → A: **Committed allowlist + seed-random** — select N issuers via fixed seed from a versioned ticker allowlist aligned with public benchmark overlap and project fixtures; not unbounded SEC registrant crawling.
- Q: What publish approval workflow applies before a dataset version is committed and registered? → A: **Draft + explicit publish** — generation produces a draft bundle and report automatically; an operator reviews the manifest/generation report and runs an explicit publish command before the version is committed and registered.
- Q: What inspiration profile mix should v1 target across FinanceBench-, FinDER-, and FinAgentBench-style generation? → A: **Config-only quotas** — profile mix is fully defined in generation config (no hard-coded split in code); the **shipped v1 default config** uses **equal thirds** (~33% per style).
- Q: What is the default corpus bundle storage model for offline evaluation? → A: **Git LFS default** — corpus binaries stored in Git LFS; manifest records content-addressed hashes for verification.
- Q: Must generation and evaluation share the same judge model version pin? → A: **Separate models allowed** — generation and evaluation record independent model pins; **v1 default config uses the same Gemini model** for both generation and evaluation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Reproducible Issuer and Filing Sampling (Priority: P1)

An evaluation engineer defines a generation run by choosing how many issuers and filings to include, with a fixed random seed and documented sampling rules, so the same run configuration always selects the same issuer–filing set.

**Why this priority**: Without reproducible sampling, generated datasets cannot be compared, extended, or audited.

**Independent Test**: Run sampling twice with the same seed and configuration; verify identical issuer list, filing accession list, and sampling manifest hash.

**Acceptance Scenarios**:

1. **Given** a generation config with seed, issuer count, and filing filters (form types, period range), **When** sampling runs, **Then** a sampling manifest records seed, filters, selected tickers/CIKs drawn seed-randomly from the committed allowlist, and chosen accessions with rationale tags (e.g., latest 10-K, paired 10-Q).
2. **Given** two engineers use the same seed and config on different machines, **When** they run sampling, **Then** they produce identical sampling manifests before any network ingestion begins.
3. **Given** rate-limit or storage budget caps in config, **When** sampling would exceed caps, **Then** the run stops with a clear budget-exceeded report before ingestion starts.

---

### User Story 2 - Production Pipeline Materialization of Sampled Corpus (Priority: P1)

A researcher materializes the sampled filings through the same production Docling/XBRL ingestion and graph materialization path used for live queries, producing a frozen snapshot bundled with the generated dataset.

**Why this priority**: Custom benchmark items must reference the same structural graph the agent traverses in production; ad-hoc parsing would invalidate evaluation.

**Independent Test**: Materialize a small sample (e.g., 3 issuers, 5 filings); verify snapshot id, reachability audit, and that parsed artifacts are stored under the dataset bundle—not fetched again at evaluation time.

**Acceptance Scenarios**:

1. **Given** a sampling manifest, **When** corpus materialization runs, **Then** each accession passes through production Docling/XBRL ingestion and graph build, yielding a snapshot id linked in the dataset manifest.
2. **Given** materialization completes, **When** an operator inspects the dataset bundle, **Then** raw filings, parsed outputs, and graph snapshot metadata are present for offline evaluation without live EDGAR access (corpus binaries retrieved via Git LFS per manifest hashes).
3. **Given** a filing fails ingestion validation, **When** materialization runs, **Then** the failure is recorded in the generation report and excluded filings do not produce benchmark items.

---

### User Story 3 - Judge-Assisted Question and Ground-Truth Generation (Priority: P1)

An evaluation engineer uses an external judge model to generate benchmark items from materialized filing content: natural-language questions, gold answers or rubrics, expected filing sets, and expected section paths—styled after question taxonomies documented in FinDER, FinAgentBench, and FinanceBench research.

**Why this priority**: This is the core value— a project-native benchmark grounded in real SEC/XBRL structure rather than only adapting third-party corpora.

**Independent Test**: Generate items for one issuer snapshot; verify each item has question text, judgment block (numeric gold answer or rubric), expected filing set, and at least one expected section path resolvable in the materialized graph.

**Acceptance Scenarios**:

1. **Given** a materialized snapshot and generation prompt profile inspired by [FinanceBench](https://github.com/patronus-ai/financebench) (metrics, domain-relevant, novel reasoning types), **When** the judge generation step runs, **Then** produced items include question type tags aligned to those categories where applicable.
2. **Given** FinDER-style retrieval QA ([HF FinDER](https://huggingface.co/datasets/Linq-AI-Research/FinDER), arXiv:2504.15800), **When** generation runs with the FinDER profile, **Then** items include reference-evidence rubrics suitable for retrieval-fidelity scoring.
3. **Given** FinAgentBench agentic retrieval patterns ([Kaggle ICAIF challenge](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data), arXiv:2508.14052), **When** generation runs with the agentic profile, **Then** multi-filing items specify expected filing sets and section paths spanning more than one accession where the profile requires it.
4. **Given** a generated item, **When** validated, **Then** expected section paths resolve to nodes present in the bundled snapshot graph (or the item is rejected with validation errors).

---

### User Story 4 - Versioned Dataset Bundle and Registry Plug-In (Priority: P2)

A release engineer publishes a versioned custom dataset (manifest, item files, bundled corpus snapshot, generation provenance) and registers it in the modular benchmark registry so evaluation runs consume it like any other dataset—without changing retrieval code.

**Why this priority**: Connects generated data to existing evaluation and judge infrastructure (features 001, 010, 011).

**Independent Test**: Register dataset `custom-judge-v1`; load dev split via registry; run evaluation offline (no EDGAR); verify items load and reference bundled snapshot id.

**Acceptance Scenarios**:

1. **Given** a completed generation run, **When** validation passes the publish threshold, **Then** a **draft** dataset bundle and generation report are produced but the version is not yet registered or committed as published.
2. **Given** an operator reviews the draft manifest and generation report, **When** they run the explicit publish command, **Then** the dataset version is committed, registered, and eligible for evaluation runs; the manifest records both judge version pins.
3. **Given** the dataset is registered, **When** an evaluation suite references it, **Then** the runner loads items and frozen corpus from the bundle (via Git LFS) without live EDGAR fetches.
4. **Given** a dataset version is deprecated, **When** unregistered, **Then** evaluation fails fast with “dataset not registered” and production retrieval remains unchanged.

---

### User Story 5 - CLI Reproduce and Extend (Priority: P2)

An engineer reproduces the full dataset from documented config or extends an existing version by adding issuers/items under a new version id, with governance limits enforced throughout.

**Why this priority**: Success criterion requires third-party reproduction and extension without ad-hoc scripts.

**Independent Test**: Follow quickstart on a clean machine with bundled corpus only; reproduce manifest hash. Run extend command with new seed slice; verify new version id and incremented item count.

**Acceptance Scenarios**:

1. **Given** committed generation config and seed, **When** `reproduce` CLI runs on a machine without EDGAR access, **Then** the reproduced item manifest hash matches the published version (using bundled corpus artifacts).
2. **Given** an existing dataset v1, **When** `extend` runs with additional issuer sample and budget caps, **Then** v2 manifest documents parent version, added items, and new snapshot bindings.
3. **Given** judge API rate limits during generation, **When** limits are hit, **Then** the CLI checkpoints progress, respects backoff, and resumes without duplicating accepted items.

---

### Edge Cases

- Sampled issuer delisted or filing unavailable at generation time: skip with logged reason; do not substitute a random alternate without seed-driven fallback rules documented in config.
- Judge produces hallucinated section paths: validation rejects item; retry budget per filing before abandoning.
- Storage budget exceeded mid-materialization: halt with partial snapshot marked invalid; no draft or published dataset version created.
- Duplicate questions across items (near-duplicate text): deduplication pass flags or merges per configurable similarity threshold in manifest.
- Extend run conflicts with frozen parent snapshot: extension MUST either reuse parent snapshot for unchanged issuers or document a new snapshot id for the combined bundle.
- Offline reproduction missing bundled binary artifacts: fail with explicit missing-artifact list (including Git LFS pull instructions), not silent synthetic items.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a generation workflow that samples issuers and filings with configurable filters, fixed random seed, and a persisted sampling manifest. Issuer selection MUST draw seed-randomly from a **versioned committed allowlist** (benchmark-aligned tickers plus project fixtures)—not from an unbounded SEC registrant crawl.
- **FR-016**: The committed issuer allowlist MUST be versioned in the repository, document provenance (benchmark overlap sources), and be referenced by hash in each sampling manifest.
- **FR-002**: Sampled filings MUST be ingested and materialized through the production Docling/XBRL pipeline and graph build path used for live queries.
- **FR-003**: Generated benchmark items MUST include: stable item id, question text, gold answer and/or rubric, expected filing set (accessions or fiscal scope), and expected section paths resolvable against the bundled graph.
- **FR-004**: Question generation MUST support inspiration profiles derived from FinDER, FinAgentBench, and FinanceBench taxonomies (metrics, domain-relevant, novel, retrieval-evidence, agentic multi-hop)—documented in generation config, not hard-coded in retrieval. Profile **mix quotas** MUST be configurable per run; the **v1 default generation config** MUST specify **equal thirds** (~33% FinanceBench-style, ~33% FinDER-style, ~33% FinAgentBench-style).
- **FR-005**: An external judge model MUST produce or refine questions and ground truth from materialized filing content. Generation config MUST record **`generation_judge_version`** independently from evaluation. Different model families are permitted; the **v1 default config pins the same Gemini model** for generation and evaluation.
- **FR-006**: The published dataset bundle MUST include everything required for evaluation without live EDGAR access: item files, dataset manifest, corpus snapshot reference, and stored parsed/graph artifacts or equivalent offline bundle.
- **FR-007**: The system MUST enforce governance caps configurable per run: maximum issuers, maximum filings, maximum judge API calls, maximum storage bytes, and maximum wall-clock duration—with fail-stop behavior and audit logs when exceeded.
- **FR-008**: All stochastic steps (issuer sampling, filing subsampling, item subset selection) MUST be driven by documented seeds recorded in the dataset manifest.
- **FR-009**: The system MUST validate each generated item: required fields present, expected filings exist in snapshot, expected section paths resolve in graph, gold answer or rubric non-empty unless explicitly marked rubric-only.
- **FR-010**: The custom dataset MUST register as a plug-in benchmark dataset (compatible with feature 011 registry contract) without modifying retrieval, ingestion orchestration, or graph navigation code.
- **FR-011**: CLI MUST support at minimum: `generate` (full pipeline to draft), `publish` (promote draft to committed/registered version after operator review), `reproduce` (rebuild from pinned config + bundle), and `extend` (new version from parent + delta config).
- **FR-012**: Published datasets MUST be versioned in the repository with manifest, generation config, and item files; **corpus bundles MUST use Git LFS by default** (content-addressed hashes in manifest for verification). External cache URLs MAY be documented as an optional fallback when LFS is unavailable, but LFS is the canonical v1 distribution path.
- **FR-013**: Documentation MUST enable a third party to reproduce the dataset in under 60 minutes on a machine with bundled artifacts (excluding optional re-download of upstream benchmark reference data).
- **FR-014**: Generation MUST NOT run silently when using placeholder or synthetic items; production datasets require explicit validation pass rate threshold (≥95% items accepted) before a **draft** is eligible for publish; publish MUST require an explicit operator command after review of the generation report.
- **FR-015**: Evaluation runs consuming this dataset MUST record dataset version, snapshot id, generation seed, **`generation_judge_version`**, and **`evaluation_judge_version`** alongside standard benchmark run metadata (feature 010 alignment).

### Key Entities

- **GenerationConfig**: Seed, issuer count/filters, filing filters, allowlist version/hash, inspiration profiles and **per-profile item quotas**, governance caps, **`generation_judge_version`** pin, optional **`evaluation_judge_version`** override (defaults to same pin in v1 config).
- **IssuerAllowlist**: Version id, ticker/CIK entries, provenance note (benchmark overlap), content hash.
- **SamplingManifest**: Selected issuers, accessions, seed, timestamp, config hash, budget consumption snapshot.
- **CorpusBundle**: Snapshot id, stored filings, parsed artifacts, graph export, reachability audit result, total byte size.
- **GeneratedBenchmarkItem**: Question, type tag, gold answer or rubric, expected filing set, expected section paths, optional chunk-id bindings post-validation.
- **DatasetManifest**: Version id, item count, content hash, parent version (if extended), generation config reference, corpus bundle reference, benchmark inspiration citations, **`generation_judge_version`**, **`evaluation_judge_version`** (may differ; v1 default: same Gemini pin).
- **GenerationReport**: Accepted/rejected item counts, validation failures, budget usage, judge call counts, duration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A published custom dataset contains **≥200** validated benchmark items with a versioned manifest committed to the repository; the published generation config documents per-profile quotas (v1 default: equal thirds across FinanceBench-, FinDER-, and FinAgentBench-style profiles).
- **SC-002**: A third party can run evaluation on the full dataset using only bundled corpus artifacts—**zero live EDGAR fetches** during evaluation—documented in quickstart and verified by offline test.
- **SC-003**: Reproduce CLI on a clean environment reproduces the **same item manifest hash** as the published version when using pinned config and bundle.
- **SC-004**: **≥95%** of judge-generated item candidates pass structural validation (filing set + section path resolution) before publish; failures are logged in generation report.
- **SC-005**: Generation config documents seed, governance caps, and **both judge version pins** such that two independent runs with identical inputs produce **identical sampling manifests** (before network variance from ingestion retries); v1 default uses the same Gemini pin for generation and evaluation.
- **SC-006**: Dataset registers in the benchmark plug-in registry and completes an end-to-end evaluation smoke run (≥20 items) with trajectory validation and external judge scoring per feature 010.
- **SC-007**: Extend CLI produces a new semantic version with documented delta (added issuers, items, snapshot changes) without mutating the parent version’s committed artifacts.

## Assumptions

- **Judge model**: Generation and evaluation use **independently recorded model pins** (`generation_judge_version`, `evaluation_judge_version`); different model families are allowed. The **v1 default generation config uses the same Gemini model** for both generation and evaluation; operators may diverge pins in custom configs.
- **Benchmark inspiration**: FinDER, FinAgentBench, and FinanceBench are **templates for question style and taxonomy**, not bulk-imported row copies—generated items are grounded in the project’s own materialized SEC/XBRL corpus. Reference: [FinDER](https://huggingface.co/datasets/Linq-AI-Research/FinDER), [FinanceBench](https://github.com/patronus-ai/financebench), [FinAgentBench Kaggle](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data). **v1 default config** targets equal thirds across the three inspiration styles; operators may override quotas in custom configs.
- **Initial scale**: v1 targets ≥200 items across ≥8 issuers unless storage budget config sets a lower cap with documented rationale.
- **Issuer allowlist**: v1 uses a committed allowlist aligned with issuers in FinDER, FinanceBench open-source, FinAgentBench challenge data, and existing project fixtures; seed-random subset selection per FR-001/FR-016.
- **Relationship to feature 011**: Feature 011 adapts public benchmarks; this feature **creates a native custom benchmark** that may later register alongside them—shared registry contract, separate generation pipeline.
- **Corpus storage**: v1 corpus bundles use **Git LFS** as the default distribution mechanism; manifests always store content hashes for integrity verification. External cache documented only as optional fallback when LFS pull is not possible.
- **Rate limits**: Judge and EDGAR fetch limits use conservative defaults with exponential backoff; generation is batch/offline, not latency-sensitive.

## References

| Resource | Link | Role |
|----------|------|------|
| FinDER | [Hugging Face](https://huggingface.co/datasets/Linq-AI-Research/FinDER) / [arXiv:2504.15800](https://arxiv.org/abs/2504.15800) | Retrieval QA and evidence rubric patterns |
| FinanceBench | [GitHub](https://github.com/patronus-ai/financebench) / [arXiv:2311.11944](https://arxiv.org/abs/2311.11944) | Question types: metrics, domain-relevant, novel |
| FinAgentBench | [Kaggle ICAIF 25](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data) / arXiv:2508.14052 | Agentic multi-filing retrieval patterns |
| Benchmark registry | [001 contract](../001-sec-disclosure-rag/contracts/benchmark-registry.md) | Plug-in registration |
| Public benchmark adapters | *(planned)* | Related complementary feature: adapts upstream benchmarks rather than generating native corpus |
| Trajectory judge | [010 spec](../010-mlflow-trajectory-judge-eval/spec.md) | Evaluation and judge version pinning |

## Out of Scope (v1)

- Fully automated publish without operator review (draft + explicit `publish` is required).
- Human-in-the-loop annotation UI for editing generated items (CLI/config edits only).
- Training or fine-tuning judge or retrieval models on generated data.
- Hosting generated datasets for public download outside the repository bundle policy.
- Replacing FinDER/FinanceBench/FinAgentBench adapters from feature 011.
- Guaranteeing item parity with any upstream benchmark’s gold labels (inspiration only, not replication).
