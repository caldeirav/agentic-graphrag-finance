## Title

Graph-Grounded Agentic Retrieval: Multi-Stage Reasoning over XBRL Financial Disclosures

## Abstract

Large language model agents show promise on open-domain reasoning, but financial question answering over regulatory filings remains difficult. Filings are long, structurally heterogeneous, and split across machine-readable XBRL facts and narrative HTML. Flat chunking and single-shot retrieval often miss filing scope, section structure, and the distinction between numeric tables and prose.

This research develops an **agentic graph retrieval** approach for SEC **10-K** and **10-Q** disclosures. Raw EDGAR packages are parsed with **Docling**, mapped into hierarchical knowledge graphs aligned with the **docling-graph** schema, and queried by a **multi-stage LangGraph agent** that binds filings and time periods, routes to sections, extracts evidence at chunk granularity, and synthesizes grounded answers with explicit citations. An external trajectory judge scores both answer quality and navigation fidelity.

Evaluation is built around a **frozen, graph-grounded benchmark** of roughly two hundred development items drawn from a reproducible issuer sample. Items are authored in the style of—but not copied from—public financial QA benchmarks (**FinanceBench**, **FinDER**, **FinAgentBench**), with binding metadata that ties each question to real accessions and resolvable section paths. Experiments compare the full graph agent against dense retrieval and ablated variants that remove macro routing, graph walking, or HTML narrative access. The goal is to quantify when structural navigation improves outcome accuracy, citation ranking, and interpretable trajectories relative to strong non-graph baselines.

This document describes the **research direction and methodology** as it is being implemented and refined; it is not a report of final conclusions.

---

## Research problem

Financial analysts and researchers routinely ask questions that require:

1. **Correct filing scope** — e.g. distinguishing annual **10-K** from quarterly **10-Q**, or binding two filings for year-over-year comparison.
2. **Structural navigation** — locating **Item 7 (MD&A)**, **Risk Factors**, segment footnotes, or XBRL fact tables rather than retrieving arbitrary similar paragraphs.
3. **Evidence-grounded answers** — numeric and narrative claims must be traceable to cited chunks or facts in the source filing.
4. **Auditable agent behavior** — intermediate routing decisions should be inspectable, not only final strings.

Generic retrieval-augmented generation (RAG) pipelines treat filings as flat text collections. That design underuses the regulatory structure that XBRL and EDGAR already provide, and it complicates fair evaluation of *agentic* retrieval—systems that must decide *where* to look before *what* to quote.

---

## Research approach

### 1. Data ingestion and graph construction

The foundation is a reproducible pipeline from EDGAR download to queryable graph snapshots per issuer.

**Parsing.** SEC filing packages (HTML instance documents, taxonomy linkbases, and related artifacts) are processed with **Docling** and XBRL-aware tooling. The output is a normalized document representation that preserves tables, labeled facts, and narrative blocks rather than collapsing everything into unstructured text.

**Graph mapping.** Parsed material is mapped into a **hierarchical knowledge graph** whose node types include filing-level, section-level, and chunk-level entities (paragraphs, table regions, XBRL facts). Edges encode regulatory structure (parent/child sections), containment (section → chunk), and cross-filing temporal relationships where multiple snapshots are materialized for one issuer. The graph schema follows the **docling-graph** contract so that navigation semantics remain portable and documented.

**Reachability and audit.** Each materialized snapshot is accompanied by structural metadata (manifest of filings, node index, reachability checks) so that downstream agents and evaluators can verify that expected sections and chunks exist before a question is scored.

**Design choice.** Because XBRL filings are already structured, graph construction is largely **deterministic** from parsed facts and section headings, rather than relying on open-ended LLM extraction from PDF layout—a pattern common in general docling-graph tutorials but ill-suited to tagged regulatory data.

### 2. Multi-stage agentic retrieval

The agent is organized as a staged **LangGraph** workflow. Each stage emits trace payloads suitable for logging and external review.

| Stage | Role | Typical decisions |
|-------|------|-------------------|
| **Macro routing** | Bind query to one or more filings and a temporal anchor | Map “latest annual report” → 10-K; “prior quarter” → specific 10-Q; comparison queries → two accessions |
| **Intent routing** | Classify information need | Numeric vs qualitative emphasis; comparison vs point lookup |
| **Meso routing** | Navigate section structure | TOC planning, section scoring, graph walking to candidate MD&A / risk / footnote regions |
| **Micro extraction** | Rank evidence within sections | Score chunks and XBRL facts by relevance; respect xbrl-only vs HTML narrative modes |
| **Synthesis** | Produce cited answer | Ground claims in retrieved evidence; apply abstention and numeric grounding guards where evidence is weak |

**Graph walking** distinguishes this design from embedding-only retrieval: the agent follows explicit section and chunk nodes instead of relying solely on vector similarity over a flat index.

**Synthesis constraints.** Answers are required to cite chunk identifiers in retrieval order. Additional logic targets known failure modes in finance QA—ungrounded numerics, comparison answers without dual-filing support, and mismatches between retrieved XBRL facts and narrative labels.

### 3. Trajectory logging and external judging

Every interactive or benchmark run records an **agent trajectory**: stage transitions, binding proposals, visited sections, ranked chunks, and final citations. A **blocking external judge** (Gemini-class model with a fixed rubric configuration) evaluates:

- **Value alignment** — agreement between the agent answer and human-authored ground truth where available.
- **Trajectory fidelity** — whether navigation and retrieval behavior plausibly support the answer.

Separating **outcome** scoring from **process** scoring allows analysis of cases where retrieval ranking is strong but synthesis fails, or vice versa— a pattern that aggregate accuracy alone would obscure.

---

## Evaluation methodology

### Custom graph-grounded benchmark

Rather than importing third-party benchmark rows directly, the project generates a **native evaluation set** over the same frozen EDGAR-derived graphs used in production. Generation proceeds in phases:

1. **Sampling** — Reproducible draw of issuers and filings from a curated allowlist spanning sectors represented in public financial QA resources.
2. **Materialization** — Build graph snapshots through the identical ingest path used for live queries.
3. **Item authoring** — An LLM author proposes questions and ground-truth answers constrained by graph-resolvable bindings (`expected_accessions`, `expected_section_paths`).
4. **Validation** — Reject items whose bindings are infeasible, duplicate near-identical questions, or fail profile-specific rules (e.g. multi-filing items must reference at least two accessions).
5. **Publish** — Freeze corpus hashes, item hashes, and **relevance labels** (chunk IDs deemed relevant per item) for offline reproduction.

The current development split targets **200 items** with **100% answer ground truth**, quota-balanced across three **inspiration profiles** (see below). Comparison-style items require structured answers and atomic **required claims** (per-filing facts plus cross-filing synthesis), not boilerplate templates.

### Metrics

| Category | Metrics | Purpose |
|----------|---------|---------|
| **Outcome** | Task success (mean value alignment over all eligible items) | Primary headline accuracy |
| **Retrieval ranking** | MRR, MAP, nDCG@10 over citation lists vs graph-grounded relevance labels | Measure whether cited chunks match labeled evidence |
| **Process** | Trajectory fidelity (judge rubric) | Reward sensible routing and retrieval |
| **Structural** | Accession binding accuracy, section-path hit rate | Audit macro/meso alignment with expected bindings |

Ranking metrics are computed from the **ordered citation list** in the agent answer against materialized relevance labels—not from internal ranker scores alone—so improvements in synthesis and citation ordering both surface in evaluation.

### Experimental variants

Experiments are designed around a **full graph agent** and controlled ablations on the same frozen item set:

| Variant | What is removed or changed | Research question |
|---------|---------------------------|-------------------|
| **Graph-full** | None (baseline) | How well does full macro → meso → micro navigation perform? |
| **Flat-chunk** | Graph walker; dense MiniLM embedding retrieval over the same chunks | How much does structural navigation add over strong flat RAG? |
| **No-macro** | Macro router; filings pre-bound from item metadata | How much does free-form filing selection matter when bindings are given? |
| **No-walker** | Meso and micro graph hops | Can intent + synthesis compensate without section traversal? |
| **XBRL-only** | HTML narrative chunks excluded | How dependent is performance on prose vs tagged facts? |

**Stratified analysis** by primary evidence source (HTML narrative, XBRL, mixed) is planned to avoid pooling ablation comparisons where variants are structurally incapable of retrieving certain evidence types (e.g. HTML-labeled items under a no-walker or xbrl-only configuration).

### Reproducibility protocol

Benchmark evaluation runs **offline** against the published bundle—no live EDGAR fetches during scoring—so all variants see identical corpora. A release manifest pins corpus, item, and relevance-label hashes; exported aggregate tables can be checked against stored checksums after full multi-variant runs. Judge batches may be deferred and resumed so long agent runs remain practical at dev-split scale.

---

## Inspiring benchmarks and datasets

Public financial QA resources inform **question style, difficulty, and validation rules**. They do not supply the evaluation rows directly; every item is regenerated against project graphs.

### FinanceBench

**FinanceBench** (Isenberg et al., [*FinanceBench: A New Benchmark for Financial Question Answering*](https://arxiv.org/abs/2311.11944); [patronus-ai/financebench](https://github.com/patronus-ai/financebench)) provides expert-verified questions over long **10-K**-style documents, including metrics-generated, domain-relevant, and novel-generated types.

**Adaptation.** The **financebench** inspiration profile borrows this taxonomy and the expectation of concise numeric or textual gold answers. Items bind to **graph-resolvable section paths** instead of PDF page indices, and ground truth is validated against the materialized node index.

### FinDER

**FinDER** (Linq-AI-Research, [*FinDER: Financial Dataset for Question Answering and Evaluating Retrieval-Augmented Generation*](https://arxiv.org/abs/2504.15800); [Hugging Face dataset](https://huggingface.co/datasets/Linq-AI-Research/FinDER)) emphasizes ambiguous, retrieval-centric financial questions with evidence-focused evaluation.

**Adaptation.** The **finder** profile stresses retrieval difficulty and narrative grounding. Current benchmark generations require explicit **answer ground truth** and **required claims** on narrative answers so that headline scoring uses a unified value-alignment criterion rather than rubric-only subsets.

### FinAgentBench

**FinAgentBench** ([*FinAgentBench: A Benchmark Dataset for Agentic Retrieval in Financial Question Answering*](https://arxiv.org/abs/2508.14052); [ACM ICAIF '25 Agentic Retrieval Grand Challenge](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data)) targets **multi-stage, multi-filing** agentic retrieval—choosing the right filing before extracting evidence.

**Adaptation.** The **finagentbench** profile requires **at least two accessions** per item and **comparison-structured** answers with per-filing and cross-filing atomic claims. A floor on multi-filing items ensures the dev split exercises macro binding and cross-document synthesis, not only single-filing lookups.

### EDGAR-CORPUS

**EDGAR-CORPUS** (Loukas et al., [*EDGAR-CORPUS: Billions of Tokens Make The World Go Round*](https://arxiv.org/abs/2109.14394); [Hugging Face dataset](https://huggingface.co/datasets/eloukas/edgar-corpus)) demonstrates large-scale construction of clean text from SEC HTML filings.

**Role in this research.** EDGAR-CORPUS informs **corpus scale and cleaning lessons** for ingestion, but the present system prioritizes **structured XBRL graphs** over token-level dumps alone. It serves as a reference for scaling ingestion while the evaluation focus stays on graph-navigable snapshots and agent trajectories.

### Profile balance

The development split aims for roughly equal representation across the three inspiration profiles (on the order of **68 / 66 / 66** items), selected deterministically from a larger accepted pool so that profile quotas are met without sacrificing binding feasibility.

---

## Preliminary observations and open questions

Early full-scale reproduction runs on the frozen two-hundred-item split (five variants, external judge, deferred judge batching) suggest several patterns that motivate continued work—reported here as **hypotheses under active investigation**, not final claims:

- **Retrieval vs outcome.** Graph-full agents can achieve strong citation ranking (high MRR) while value alignment remains moderate, indicating synthesis and grounding—not retrieval alone—as a dominant error mode on narrative-heavy items.
- **Ablation asymmetry.** Variants that cannot reach HTML narrative chunks show near-zero ranking and outcome on HTML-stratified items, as expected; pooled aggregates can mask this unless reported by evidence stratum.
- **Flat dense baseline.** A MiniLM flat-chunk baseline remains competitive on some ranking metrics but lags on task success when questions require correct filing scope and section fidelity—consistent with the design intent of macro and meso stages.
- **Ordering anomalies.** Occasional cases where an ablation without macro routing slightly exceeds the full agent on pooled outcome accuracy underscore the need for stratum-aware reporting and item-level drill-down before drawing architectural conclusions.

Open research questions include:

1. How much of outcome error is attributable to **macro mis-binding** vs **meso section selection** vs **synthesis**?
2. Can **deterministic synthesis paths** (comparison, divestiture, segment tables) reduce judge variance without harming generalization?
3. What is the minimum **graph schema richness** needed to beat flat RAG at fixed citation budget?
4. How should **multi-filing comparison** items be scored when partially correct per-filing evidence is retrieved but cross-filing synthesis is wrong?

---

## Expected contributions

1. **A reproducible graph construction pipeline** from EDGAR XBRL packages to docling-graph–aligned snapshots with explicit filing and section semantics.
2. **A staged agentic retrieval architecture** with logged trajectories linking macro binding, section navigation, and cited micro evidence.
3. **A graph-grounded financial QA benchmark** inspired by FinanceBench, FinDER, and FinAgentBench, with frozen corpora, relevance labels, and unified answer-ground-truth scoring.
4. **An ablation-oriented evaluation protocol** comparing graph navigation to dense retrieval and structured incapability baselines, with stratum-aware reporting.
5. **Empirical analysis** (in progress) of when structural retrieval improves outcome accuracy, citation ranking, and auditable agent behavior on regulatory disclosures.

---

## Scope and non-goals

- **In scope:** U.S. SEC **10-K** / **10-Q** XBRL filings; English-language QA; offline evaluation on frozen graphs; open-source parser and graph stack (Docling ecosystem).
- **Out of scope (current phase):** Real-time market data feeds; proprietary analyst models; multilingual filings; end-user production deployment; automatic updating of benchmarks without operator publish gates.

---

## Summary

This research investigates **graph-grounded agentic retrieval** as an alternative to flat RAG for financial disclosure QA. By combining deterministic XBRL-aware graphs, multi-stage navigation, citation-grounded synthesis, and a native benchmark rooted in public financial QA traditions, the project seeks measurable evidence on **when and why** structure-aware agents outperform strong baselines—and where they still fail. Results remain iterative; the methodology above reflects the system as it is being built and evaluated today.
