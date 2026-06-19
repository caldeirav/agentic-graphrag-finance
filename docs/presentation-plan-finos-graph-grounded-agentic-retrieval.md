# Presentation Plan: Graph-Grounded Agentic Retrieval for Multi-Stage Reasoning over XBRL Financial Disclosures

**Proposed session title:** Graph-Grounded Agentic Retrieval for Multi-Stage Reasoning over XBRL Financial Disclosures

**Suggested duration:** 45–50 minutes (+ 10 minutes Q&A)

**Primary audience:** FINOS AI Evaluation and Benchmarking stream; financial ML engineers, RAG architects, compliance-aware AI builders, open-source contributors evaluating agentic retrieval over regulated content.

**Session promise (one sentence):** Show how to turn SEC XBRL filings into auditable knowledge graphs with Docling and docling-graph, navigate them with a multi-stage LangGraph agent, and measure reasoning trajectories against a native graph-grounded benchmark inspired by FinanceBench, FinDER, and FinAgentBench.

**Open-source repo:** [agentic-graphrag-finance](https://github.com/caldeirav/agentic-graphrag-finance)

**Recommended live assets**

| Asset | URL / path |
|-------|------------|
| Interactive AAPL eval graph | [visualization.html](https://caldeirav.github.io/agentic-graphrag-finance/assets/aapl-eval-graph/visualization.html?v=2) |
| End-to-end walkthrough | [docs/end-to-end-walkthrough.md](end-to-end-walkthrough.md) |
| Paper reproduction baseline | `releases/paper-v1.0/expected_checksums.json` (`task_success` ≈ 0.467, `mrr` ≈ 0.916) |

---

## Narrative arc (maps to blog + repo docs)

```text
Problem & prior art  →  Structural thesis  →  Docling/XBRL ingest  →  Graph materialization
       →  Multi-stage agent (demo)  →  Trajectory judge  →  Benchmark generation  →  Results & blueprint
```

---

## Slide-by-slide plan

Each slide includes: **title**, **on-slide content**, **visual / demo suggestion**, and **expanded speaker notes** (detailed narrative, examples, transitions, and external references).

---

### Slide 1 — Title

**On-slide content**

- Title: *Graph-Grounded Agentic Retrieval for Multi-Stage Reasoning over XBRL Financial Disclosures*
- Subtitle: FINOS AI Evaluation and Benchmarking · Docling · docling-graph · LangGraph
- Your name / affiliation · GitHub link

**Visual:** Clean title slide; optional background motif of a filing → graph → agent path.

**Speaker notes (~1 min)**

**Opening (15–20 sec):** Greet the room and name the FINOS AI Evaluation and Benchmarking stream context. State the tension plainly: regulators and issuers have spent decades standardizing XBRL so machines can read financial statements—but most AI retrieval stacks still chunk filings like blog posts. That mismatch is not a minor formatting issue; it is why models cite the right *word* near the wrong *period*, or quote MD&A prose when the question asked for a balance-sheet line item.

**What this session is (20 sec):** Position the talk as an **architecture and evaluation blueprint**, not a vendor demo or a claim that the problem is solved. You are sharing an open-source reference implementation ([agentic-graphrag-finance](https://github.com/caldeirav/agentic-graphrag-finance)) that anyone can reproduce, inspect, and argue with. The goal is **verifiable** behavior: graph snapshots you can open, agent trajectories you can audit, benchmark rows tied to real SEC accessions.

**What this session is not:** Not a pitch for a single LLM vendor; not a promise of production-ready accuracy on every question type. Be upfront that synthesis quality is still an active research area—the value today is **structure + measurement**.

**Audience hook:** Ask rhetorically (or by show of hands): “Who has built RAG over 10-K PDFs or HTML and seen fiscal-period confusion?” You do not need a long discussion—just establish shared pain before Slide 2.

**Transition:** “Let me summarize what we will cover in the next forty-five minutes.”

**External references**

- FINOS AI initiatives (context for stream): [FINOS](https://www.finos.org/)
- Project README: [README.md](../README.md)

---

### Slide 2 — Session abstract (what you will leave with)

**On-slide content**

- **Problem:** XBRL + narrative HTML are structured; flat chunk RAG loses filing scope, sections, and fact linkage.
- **Approach:** Docling parse → docling-graph–aligned KG → five-stage LangGraph agent → Gemini trajectory judge.
- **Evidence:** Native 200-item benchmark (FinanceBench / FinDER / FinAgentBench *styles*); five variant ablations; frozen corpus.
- **Takeaway:** Blueprint for high-precision, auditable retrieval over regulated disclosures.

**Visual:** Four-quadrant or vertical stack matching the bullets.

**Speaker notes (~2 min)**

**Walk the four bullets on the slide** in order—each maps to a section of the talk:

1. **Problem:** XBRL gives you tagged facts; HTML gives you narrative and footnotes; EDGAR gives you Item 1A vs Item 7 hierarchy. Flat chunk RAG throws all of that into one embedding index, so the retriever never explicitly decides *which filing* or *which section* before grabbing text. Name the failure modes: wrong fiscal year, wrong form type (10-Q vs 10-K), narrative retrieved when the answer was an XBRL fact.

2. **Approach:** Name the stack once here so the audience has a mental map before you dive in: **Docling** parses XBRL packages; a deterministic mapper builds **docling-graph–aligned** snapshots; a **five-stage LangGraph agent** navigates those graphs; a **Gemini trajectory judge** scores both the answer and the path taken. Local reasoning can run on **LM Studio**; evaluation artifacts land in **MLflow**.

3. **Evidence:** Stress that benchmarks are **native**—200 items on a frozen corpus, styled after FinanceBench, FinDER, and FinAgentBench but **not copied** from them. Five system variants (full agent vs flat RAG vs ablations) run offline so every variant sees identical filings. This is the FINOS-relevant part: reproducible numbers with hash-verified tables.

4. **Takeaway:** Repeat the session promise in one sentence: leave with a **blueprint** for high-precision, auditable retrieval over regulated content—not just a diagram, but CLI commands, graph exports, and an evaluation protocol.

**Key phrase to land:** “We evaluate the **reasoning trajectory**, not only the final string.” In regulated finance, *how* the system navigated matters for trust and for debugging.

**Preview three proof points** so the audience knows where the “show me” moments are:
- (1) **Graph shape** — interactive AAPL subgraph; three question types, three paths.
- (2) **Agent trace** — YoY net sales question through macro → synthesis with citations.
- (3) **Benchmark generation** — how Gemini-authored items are grounded and validated against `graph_node_index.json`.

**Transition:** “First, why is this hard? Because analysts do not ‘vector search’ a filing—they navigate it.”

---

### Slide 3 — Why financial QA is hard (the analyst mental model)

**On-slide content**

Analysts answer in **three decisions**, not one similarity search:

1. **Which filing(s)?** 10-K vs 10-Q; latest annual vs prior quarter; comparison pairs.
2. **Which section?** MD&A (Item 7), Risk Factors (Item 1A), footnotes—not “similar paragraphs.”
3. **Which evidence?** XBRL fact, table row, narrative footnote tied to a cell.

**Visual:** Simple decision tree: Question → Filing → Section → Evidence → Answer.

**Speaker notes (~2 min)**

**Frame the three bullets as a decision ladder**, not a retrieval pipeline. When a sell-side or buy-side analyst answers a question over disclosures, they implicitly run three filters before quoting evidence:

1. **Which filing(s)?** This is scope. “Latest annual report” means the most recent **10-K**, not the last 10-Q that happened to mention revenue. “Year over year” means **two** filings with aligned fiscal calendars—not two chunks from the same filing. Comparison questions are macro-binding problems first.

2. **Which section?** Regulatory items are not interchangeable. Risk Factors (Item 1A) and MD&A (Item 7) can both mention “supply chain,” but they serve different disclosure purposes. Segment footnotes live elsewhere again. Similarity search does not know Item boundaries unless you preserve them in the index.

3. **Which evidence?** Even inside the right section, evidence types differ: an **XBRL fact** (concept + period + value), a **table row**, a **footnote** tied to a cell, or narrative prose. Numbers without period metadata are ambiguous; prose without a linked fact can be directionally right but unverifiable.

**Concrete failure story (30 sec):** Walk through “What was inventory at fiscal year-end?” Flat RAG might return (a) COGS discussion from MD&A, (b) a Q2 10-Q chunk because “inventory” appeared recently, or (c) a table fragment with the word “inventory” but the wrong column. The embedding was “close enough”; the answer is not audit-ready.

**Contrast with agentic graph retrieval:** Each decision becomes an explicit stage with logged output—macro binding, section routing, chunk ranking—so when the answer is wrong, you can see *which* decision failed.

**Audience note:** If the room includes compliance or model-risk folks, nod to them here: audit trails require **decision decomposition**, not a single retrieval score.

**Transition:** “To build the graph, we first need to respect what a filing actually contains under the hood.”

**Source:** Blog § “The structural shape of financial data”; [research-proposal.md § Research problem](research-proposal.md#research-problem).

---

### Slide 4 — What a filing actually contains

**On-slide content**

| Layer | What it is | Why it matters for AI |
|-------|------------|------------------------|
| **XBRL instance** | Tagged facts (concept + period + value) | Machine-verifiable numbers |
| **Taxonomy / linkbases** | US-GAAP dictionary, calculations, labels | Correct concept resolution |
| **HTML narrative** | MD&A, risk factors, footnotes | Qualitative “why” behind numbers |
| **Regulatory structure** | Item 1A, Item 7, etc. | Navigation scaffold |

**Visual:** EDGAR package folder screenshot or diagram: `*_htm.xml`, `.xsd`, `_cal.xml`, `_lab.xml`.

**Speaker notes (~2 min)**

**Correct a common misconception first:** Many teams start with “download the 10-K PDF.” SEC **XBRL submissions** are structured packages: an instance document (`*_htm.xml`), taxonomy files (`.xsd`), and linkbases (`_cal`, `_def`, `_lab`, `_pre`) that define calculations, definitions, labels, and presentation. Optional **HTML narrative** exhibits carry MD&A and risk-factor prose. Our pipeline treats the package as the source of truth—not a OCR or vision pass over a PDF.

**Walk the table row by row:**

- **XBRL instance:** Each **fact** is a tuple: US-GAAP **concept**, **period** (instant or duration), **value**, often **unit** and **decimals**. This is what makes “$391.04 billion revenue for FY2024” machine-checkable rather than extracted from a paragraph.

- **Taxonomy / linkbases:** Companies do not invent ad hoc tag names for core line items; they map into **US-GAAP**. Linkbases tell validators (and parsers) how concepts relate—e.g. how “Net sales” rolls up. Docling uses **Arelle** under the hood; you need the taxonomy folder local to parse offline reliably.

- **HTML narrative:** Qualitative questions—“what risks does management highlight?”—live here. Numeric questions *can* be answered from narrative, but XBRL facts are preferable for precision. A good system routes by question type.

- **Regulatory structure:** Items (1A, 7, 8, etc.) are the analyst’s table of contents. Preserving them as **SECTION** nodes is what enables meso routing to MD&A vs risk factors without semantic guessing.

**Example to say aloud:** Apple’s net sales tag is often `RevenueFromContractWithCustomerExcludingAssessedTax`—long, standardized, unambiguous once bound to a period. That becomes a **`CHUNK_XBRL_FACT`** node, not a 512-token text chunk.

**Transition:** “So if structure is available, why does flat RAG still fail in practice? Prior work quantifies it.”

**Walkthrough reference:** [end-to-end-walkthrough.md § XBRL in plain English](end-to-end-walkthrough.md#xbrl-in-plain-english).

**External references**

- SEC EDGAR overview: [sec.gov/edgar](https://www.sec.gov/edgar)
- XBRL standard: [xbrl.org](https://www.xbrl.org/)

---

### Slide 5 — Where flat RAG fails (empirical prior art)

**On-slide content**

- Generic RAG over long financial documents fails on a **large share** of expert-style questions—not because LLMs are useless, but because **filings are structured artifacts**.
- Chunking turns tables into word soup; numbers detach from sections that give them meaning.

**Visual:** Before/after: “table row in filing” vs “shredded chunks in vector DB.”

**Speaker notes (~2 min)**

**Lead with the insight, not the paper title:** FinanceBench showed that generic RAG over long financial documents fails on a **large share** of expert-style questions. The models are not useless—the **retrieval substrate** is wrong for structured disclosures. When you chunk a 200-page filing into fixed windows, three things break simultaneously: **tables** become word soup; **numbers** detach from period metadata; **sections** lose their regulatory meaning.

**Describe the “before/after” visual if you use it:** Left side—a clean table row in a filing: concept, label, FY2024 value, footnote marker. Right side—the same content split across three chunks in a vector DB, none of which contains the full fact tuple. The retriever returns a chunk that *mentions* revenue near the word “risk” because both appeared in MD&A.

**Introduce the benchmark family briefly—you will return to them on Slide 6:**

- **FinanceBench** (2023): expert-verified QA over 10-K-style documents; established that financial QA needs domain-aware evaluation, not generic QA metrics alone.
- **FinDER** (2025): emphasizes **ambiguous, retrieval-heavy** questions—good for testing whether the system finds the right *evidence*, not just a fluent answer.
- **FinAgentBench** (2025): explicitly **multi-stage, multi-filing**—choose the right filing before extracting; aligns with our macro router design.

**Important nuance for FINOS audience:** We **do not paste** FinDER or FinanceBench rows into our eval set. Public benchmarks often ship PDFs or opaque contexts that are hard to reproduce byte-for-byte. We borrow **question style and validation ideas**, then regenerate items on our frozen EDGAR graphs.

**Transition:** “Let me place our work in that landscape—what we reuse vs what we built.”

**External references**

- FinanceBench paper: [arXiv:2311.11944](https://arxiv.org/abs/2311.11944) · [patronus-ai/financebench](https://github.com/patronus-ai/financebench)
- FinDER: [arXiv:2504.15800](https://arxiv.org/abs/2504.15800) · [Hugging Face dataset](https://huggingface.co/datasets/Linq-AI-Research/FinDER)
- FinAgentBench: [arXiv:2508.14052](https://arxiv.org/abs/2508.14052) · [ACM ICAIF '25 Grand Challenge](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data)

---

### Slide 6 — Research landscape (what we build on vs what we add)

**On-slide content**

| Work | Contribution | Our relationship |
|------|--------------|------------------|
| **FinanceBench** | Expert financial QA over disclosures | Inspiration profile; numeric / domain questions |
| **FinDER** | Ambiguous retrieval-centric financial QA | Inspiration profile; narrative grounding |
| **FinAgentBench** | Multi-stage, multi-filing agentic retrieval | Inspiration profile; ≥2 accessions, comparison answers |
| **EDGAR-CORPUS** | Large-scale cleaned filing text | Ingestion scale reference; we prioritize **structured graphs** over token dumps |
| **Docling / docling-graph** | Parse + validated KG schema | Production parse + schema contract |
| **This project** | Deterministic XBRL graphs + staged agent + native benchmark | Full reproducible stack |

**Visual:** Timeline or “layers” diagram: datasets (top) → parsers (middle) → agent + eval (bottom).

**Speaker notes (~2 min)**

**Use the table as a “literature map”**—spend ~15 seconds per row, not a lecture on each paper.

**FinanceBench:** Gold-standard for *types* of financial questions (metrics-generated, domain-relevant, novel). We encode that taxonomy in our **`financebench` inspiration profile**—prompt templates that ask Gemini to author similar questions, then a validator ensures every item binds to a real `{accession}/{section_path}` in our graph index.

**FinDER:** Teaches us to write **retrieval-hard** narrative questions and to require **ground-truth answers plus required claims** in v2—so headline scoring uses one value-alignment criterion, not a separate rubric-only path for half the dataset.

**FinAgentBench:** Closest to our agent architecture: multi-hop, multi-filing. Our **`finagentbench` profile** enforces **≥2 accessions** and **comparison-structured** answers with per-filing and cross-filing atomic claims. At least 40 of our 200 dev items are multi-filing for this reason.

**EDGAR-CORPUS:** Billions of tokens of cleaned HTML text—useful reference for **ingestion at scale** and text normalization lessons. We cite it for corpus-building context, but our bet is that **XBRL graphs + section hierarchy** beat token dumps alone for agentic QA.

**Docling / docling-graph:** Not “related work” in the academic sense—they are our **production parse and schema contract**. Docling gets us from XBRL XML to structured facts; docling-graph defines the node/edge vocabulary we implement deterministically.

**This project (bottom row):** The integration layer—deterministic mapper, LangGraph agent, custom-judge benchmark, five-variant repro kit with frozen checksums.

**Emphasize once more:** Native benchmark generation is a **methodological choice** for reproducibility. If another team reruns `repro verify-corpus`, they get the same filings—not a moving target from live EDGAR.

**Transition:** “Our thesis is simple: preserve that structure in three explicit layers.”

**Full profile mapping:** [research-proposal.md § Inspiring benchmarks](research-proposal.md#inspiring-benchmarks-and-datasets).

**External references**

- EDGAR-CORPUS: [arXiv:2109.14394](https://arxiv.org/abs/2109.14394)

---

### Slide 7 — Thesis: preserve structure in three semantic layers

**On-slide content**

1. **Document-level** — filing type, accession, reporting period, temporal links between filings.
2. **Layout-level** — sections, paragraphs, footnotes; containment and reference edges.
3. **Tabular / numeric** — table rows and **XBRL facts** as first-class chunk nodes (concept, period, currency)—not arbitrary token windows.

**Visual:** Three-layer stack with example nodes (DOCUMENT → SECTION → CHUNK_XBRL_FACT).

**Speaker notes (~2 min)**

**State the design bet clearly:** When the source format is already structured—XBRL tags, HTML sections, tables—invest in a **typed graph** before scaling embeddings. **Path-finding** through labeled nodes beats **guessing** semantically similar paragraphs.

**Layer 1 — Document-level:** Each **DOCUMENT** node is one SEC accession with metadata: form type (10-K / 10-Q), period end, filed date. When multiple filings are materialized for one issuer, **TEMPORAL_TRANSITION** edges link consecutive annual reports so comparison questions have an explicit timeline—not an implicit “latest two chunks about sales.”

**Layer 2 — Layout-level:** **SECTION** nodes mirror Items and narrative regions; **CHUNK_PARAGRAPH** nodes hold MD&A and risk prose; **FOOTNOTE_OF** edges tie footnotes to tables. Containment (`CONTAINS`) encodes “this paragraph lives under Item 7.” That is how meso routing opens the right drawer in the filing cabinet.

**Layer 3 — Tabular / numeric:** **CHUNK_XBRL_FACT** nodes store one tagged number per concept **and** period, with properties (`xbrl_concept`, `period`, `currency`). Table rows get their own chunk types. Crucially, we do **not** shred facts across arbitrary 512-token windows—the fact stays atomic.

**Connect to docling-graph philosophy:** Financial knowledge graphs need **exact connections**—document contains section contains fact—not only “these embeddings are near each other.” docling-graph’s documentation stresses validated structure and explicit relationships; we adopt that contract even though we skip LLM extraction for XBRL.

**Anti-pattern to call out:** “Let’s embed all chunks and let the LLM figure it out” works for FAQ bots; it is fragile for regulated numeric QA where period and concept matter as much as wording.

**Transition:** “Here is how those layers fit in one end-to-end pipeline.”

**External references**

- docling-graph project goals: [docling-graph GitHub](https://github.com/docling-project/docling-graph) · [docling-graph docs](https://docling-project.github.io/docling-graph/)

---

### Slide 8 — Architecture overview (one pipeline slide)

**On-slide content**

```text
SEC EDGAR  →  Docling (XBRL)  →  ParsedDocument  →  GraphSnapshot (GraphML)
                                                          ↓
                                              LangGraph agent (5 stages)
                                                          ↓
                                    Trajectory export  →  Gemini judge  →  MLflow
```

Five experimental variants at eval time: `graph-full`, `flat-chunk`, `no-macro`, `no-walker`, `xbrl-only`.

**Visual:** Mermaid or simplified flowchart (from README architecture).

**Speaker notes (~2 min)**

**This is the “one slide architecture”—** audience members should photograph this or copy the ASCII. Walk left to right slowly:

1. **SEC EDGAR** — ingestion downloads full XBRL packages per accession; cached under `data/raw/sec_downloads/{ticker}/{accession}/`.

2. **Docling (XBRL)** — parses instance + taxonomy → in-memory **DoclingDocument** → our **`ParsedDocument` JSON** with sections, narrative blocks, and consolidated XBRL facts.

3. **GraphSnapshot (GraphML)** — deterministic **`docling_graph_mapper`** builds nodes/edges; **`build_snapshot`** merges multiple filings per issuer; exports GraphML, manifest, reachability audit to `data/graphs/{TICKER}/`.

4. **LangGraph agent (5 stages)** — macro → intent → meso → micro → synthesize; reads the same graph via `LocalGraphQueryAPI`; local LLM (LM Studio) for routing and synthesis.

5. **Trajectory export → Gemini judge → MLflow** — every `ask` and benchmark item produces **`agent_trajectory.json`**; validator checks completeness; external judge scores answer alignment and navigation fidelity; artifacts logged for audit.

**Name the five eval variants briefly**—you will unpack them on Slide 25: `graph-full` (baseline), `flat-chunk` (MiniLM over same chunks, no walk), `ablation-no-macro`, `ablation-no-walker`, `ablation-xbrl-only`.

**Two operator modes—make this distinction early:**
- **Interactive:** `materialize` + `ask` — one ticker, one question, live trace on stderr, judge on each query. Good for demos and debugging.
- **Paper repro:** `repro run-all` on frozen **custom-judge v2.0.0** — 200 items × 5 variants, **`OFFLINE_BENCHMARK=1`**, no live EDGAR during scoring. Good for FINOS-style reproducibility claims.

**CLI anchors:** `uv run agent-query materialize --ticker AAPL` · `uv run agent-query ask ...` · `uv run agent-query repro run-all --manifest releases/paper-v1.0/manifest.yaml`

**Transition:** “Start at the foundation: parsing XBRL with Docling.”

**Reference:** README architecture table — ingestion → parsing → graph → retrieval → evaluation.

---

### Slide 9 — Docling: parsing XBRL with Arelle (not re-inventing the parser)

**On-slide content**

- **Docling** converts XBRL instance XML + local taxonomy into a structured **DoclingDocument**.
- Backend: **Arelle** via `docling[xbrl]`; `InputFormat.XML_XBRL`.
- Output we care about: sections, HTML narrative blocks, **`xbrl-facts` table rows** (concept, value, period, currency, decimals).

**Visual:** Code snippet (minimal converter config)—keep on slide or in appendix.

```python
DocumentConverter(
    allowed_formats=[InputFormat.XML_XBRL],
    format_options={
        InputFormat.XML_XBRL: XBRLFormatOption(
            backend_options=XBRLBackendOptions(
                enable_local_fetch=True,
                enable_remote_fetch=True,
                taxonomy=accession_dir,
            )
        )
    },
)
```

**Speaker notes (~3 min)**

**Position Docling:** Open-source document intelligence from the Docling project (IBM Research roots). For this talk, ignore PDF layout models—you only need the **XBRL backend**. It is also packaged in **Red Hat AI** for teams running ingestion on OpenShift AI/Kubeflow—same library, enterprise support path. We use upstream Docling directly in the repo.

**Explain the code snippet in plain language** (do not line-by-line code review unless the room is deeply technical):
- `InputFormat.XML_XBRL` — entry point is the **instance** file, not a linkbase in isolation.
- `enable_local_fetch=True` — read taxonomy `.xsd` and linkbases from disk.
- `enable_remote_fetch=True` — for live SEC/US-GAAP, some schema references resolve online; Docling caches them. Air-gapped runs can disable remote fetch and ship a taxonomy package zip (per official Docling docs).
- `taxonomy=accession_dir` — point at the **folder containing instance + linkbases together**—a common failure mode is pointing at a zip or the wrong subdirectory.

**What Docling emits that we care about:**
- Section structure and optional **HTML narrative** blocks (MD&A, risk factors) when present in the package.
- A special table **`xbrl-facts`** whose rows are key-value lines: concept name, `value:…`, `period:…`, `currency:…`, `decimals:…`.

**Our post-Docling steps (say this—it is project-specific):**
1. **`consolidate_xbrl_fact_rows`** — merge flat rows into one record per `(concept, period)`; do not collapse periods.
2. **`format_xbrl_numeric`** — apply `decimals` scaling; SEC values are often stored in millions—raw integer `391035000000` with `decimals: -6` becomes **$391.04 billion** in human text.
3. **`fact_to_excerpt`** — stable string the graph and LLM see: `"XBRL RevenueFromContract...: $391.04 billion USD for period 2023-10-01 - 2024-09-28"`.

**Pitfall to mention:** Unpatched Docling can crash on some **typed dimensions** in Apple-style filings; we apply a small runtime patch before convert (`_apply_docling_xbrl_dimension_patch()`).

**Transition:** “Docling gives us structure; docling-graph gives us a schema contract for how to store it.”

**Walkthrough:** [end-to-end-walkthrough.md § Docling XBRL best practices](end-to-end-walkthrough.md#docling-xbrl-best-practices-and-how-we-apply-them).

**External references**

- Docling XBRL example: [XBRL Document Conversion](https://docling-project.github.io/docling/examples/xbrl_conversion/)
- Docling repo: [github.com/docling-project/docling](https://github.com/docling-project/docling)
- Red Hat AI / Docling: [Red Hat blog — modular building blocks](https://www.redhat.com/en/blog/red-hat-ai-modular-building-blocks-scalable-repeatable-model-customization)

---

### Slide 10 — Design choice: docling-graph as schema contract, not always as LLM extractor

**On-slide content**

| Upstream docling-graph tutorial | Our SEC XBRL path |
|--------------------------------|-------------------|
| PDF / report → LLM/VLM extraction pipeline | XBRL already tagged → **deterministic mapper** |
| `run_pipeline` / `docling-graph convert` | `Docling → ParsedDocument → docling_graph_mapper → GraphSnapshot` |
| Exploratory graphs from unstructured sources | Auditable GraphML + manifest per issuer |

**Visual:** Two-path fork diagram; highlight “deterministic” branch for EDGAR.

**Speaker notes (~2 min)**

**Set up the fork:** docling-graph’s **upstream tutorials** often show PDFs or unstructured reports fed through **LLM/VLM extraction pipelines** (`run_pipeline`, `docling-graph convert`) with Pydantic templates. That is the right tool when structure is **implicit** in layout and prose.

**SEC XBRL is the opposite case:** Structure is **explicit**—every material number is tagged; sections follow Item conventions; taxonomy defines concepts. Re-running LLM graph extraction on every filing would be slower, costlier, harder to audit, and would reintroduce extraction errors you do not need.

**Our path (right column of table):**
```text
Docling → ParsedDocument → docling_graph_mapper → GraphSnapshot
```
Deterministic, versioned (`DOCLING_GRAPH_MAPPER_VERSION`), fail-closed if a filing materializes with no sections and no facts.

**What we still take from docling-graph:**
- **Node and edge type vocabulary** — DOCUMENT, SECTION, CHUNK_*, CONTAINS, FOOTNOTE_OF, etc.
- **Design principles** — Pydantic validation, explicit relationships, queryable exports.
- **Visualization tooling** — we export GraphML and use docling-graph’s viz docs to explore subgraphs (AAPL demo graph in browser).

**When to use upstream CLI instead:** Exploratory graphs from **non-XBRL** PDFs, custom ontologies, research prototypes. For EDGAR 10-K/10-Q production paths, stay on this repo’s **`materialize`** command so agent semantics stay aligned with accessions.

**Transition:** “Let me walk through materialization—the `materialize` command end to end.”

**References:** `specs/004-docling-graph-materialization/research.md` (R1); blog § “Docling, XBRL, and a deterministic graph bridge.”

**External references**

- docling-graph visualization: [visualization.md](https://github.com/docling-project/docling-graph/blob/main/docs/fundamentals/graph-management/visualization.md)

---

### Slide 11 — **Drill-down:** Graph materialization pipeline (`materialize`)

**On-slide content**

Phase A — three steps:

1. **Ingest** — fetch EDGAR package → `data/raw/sec_downloads/{ticker}/{accession}/`
2. **Parse** — Docling → `ParsedDocument` JSON → `data/parsed/...`
3. **Map** — `docling_graph_mapper.map_filing()` → issuer **GraphSnapshot** (GraphML + manifest + reachability audit)

Default corpus (~2 fiscal years): e.g. 2× 10-K + 8× 10-Q (capped at 12 filings).

**Visual:** Materialize flowchart from walkthrough; show folder tree for one accession.

**Speaker notes (~3 min)**

**Introduce `materialize` as Phase A** of every workflow—nothing runs without a graph snapshot. Command: `uv run agent-query materialize --ticker AAPL`.

**Step 1 — Ingest:** Respect SEC fair access (`SEC_EDGAR_USER_AGENT`). Download or reuse cached package under `data/raw/sec_downloads/{ticker}/{accession}/`. Each folder should contain instance XML, taxonomy, linkbases, and a local **`manifest.json`** recording accession, form type, period end. Default corpus config (~2 fiscal years): roughly **2× 10-K + 8× 10-Q**, capped at 12 filings—enough for YoY and recent-quarter questions without building an entire EDGAR history.

**Step 2 — Parse:** For each accession, **`parse_xbrl_package`** invokes Docling; output saved as **`ParsedDocument` JSON** at `data/parsed/{ticker}/{accession}.json`. Optional HTML narrative merge happens here when exhibits exist.

**Step 3 — Map:** **`docling_graph_mapper.map_filing()`** per accession produces graph nodes/edges; **`build_snapshot`** unions all filings for the issuer; writes:
- `{snapshot_id}.graphml` — full graph
- `{snapshot_id}.manifest.json` — which accessions included
- `{snapshot_id}.reachability.json` — structural audit
- `index.json` — pointer to latest snapshot

**Reachability gate (compliance-relevant):** At least **95%** of XBRL/table chunks must be reachable from the document root within **≤6 structural hops**. If the graph is disconnected noise, the agent cannot be audited. Materialization **fail-closed** if a filing has zero sections and zero facts.

**Precision choice:** Materialize **every** `(concept, period)` instance—no 400-fact cap. Financial QA needs the right fact, not a sampled subset.

**Optional demo:** If pre-materialized, flash `data/graphs/AAPL/` in a file browser—audience sees tangible artifacts, not abstractions.

**Transition:** “Inside that GraphML, these are the node types the agent actually walks.”

**Deep dive:** [end-to-end-walkthrough.md § Phase A](end-to-end-walkthrough.md#phase-a-materialize--ingest-parse-build-graph).

---

### Slide 12 — Graph schema: node types the agent walks

**On-slide content**

| Node type | Role |
|-----------|------|
| `DOCUMENT` | One filing (accession) |
| `SECTION` | Item 7, Item 1A, **XBRL Financial Facts** bucket, etc. |
| `CHUNK_XBRL_FACT` | One tagged number (concept + period) |
| `CHUNK_TABLE` / `CHUNK_ROW` | Rendered financial tables |
| `CHUNK_PARAGRAPH` | HTML narrative (MD&A, risk) |

Stable IDs: e.g. `doc-{accession}-xbrl-{hash}` from concept + period.

**Visual:** Tree example from walkthrough:

```text
doc-0000320193-24-000123 [DOCUMENT]
  └── ...-xbrl-facts [SECTION]
        └── ...-xbrl-adbf72cacf40 [CHUNK_XBRL_FACT]
              source_ref: "XBRL RevenueFromContract...: $391.04 billion USD ..."
```

**Speaker notes (~2 min)**

**Walk the node type table top to bottom** as increasing granularity:

- **`DOCUMENT`** — One node per SEC accession (one 10-K or one 10-Q). Carries filing metadata the macro router uses before touching XBRL numbers.

- **`SECTION`** — Regulatory and logical regions: Item 1A, Item 7 MD&A, notes, plus a synthetic **`XBRL Financial Facts`** bucket (`xbrl_bucket`) that parents all tagged numbers for that filing. Meso routing chooses among these—not among arbitrary chunks globally.

- **`CHUNK_XBRL_FACT`** — Atomic unit for numeric QA: one US-GAAP concept in one period. Properties include `xbrl_concept`, `period`, `currency`. The **`source_ref`** field holds the human-readable excerpt from Docling.

- **`CHUNK_TABLE` / `CHUNK_ROW`** — Rendered financial tables when present—important for line items not exposed as standalone XBRL facts or for footnote-linked tables.

- **`CHUNK_PARAGRAPH`** — HTML narrative prose—required for FinDER-style risk and MD&A discussion questions.

**Stable IDs:** Example `doc-{accession}-xbrl-{hash}` derived from concept + period hash—same economic fact always maps to the same node in a given snapshot. That stability matters for **relevance labels** in the benchmark: labelers point to chunk IDs that persist across eval runs.

**Read the tree example aloud:** Document → xbrl-facts section → revenue fact node with `$391.04 billion` excerpt. This is the FinanceBench-style path in miniature.

**Implementation detail (if asked):** All models are **Pydantic-validated**; mapper version is pinned for repro diffs.

**Transition:** “Nodes tell you what exists; edges tell you how to navigate.”

**Edge catalog:** `specs/004-docling-graph-materialization/contracts/edge-catalog.md`.

---

### Slide 13 — Graph schema: edge types (navigation semantics)

**On-slide content**

| Edge | Meaning |
|------|---------|
| `CONTAINS` | Document → section → chunk hierarchy |
| `NEXT` | Reading order within a section |
| `FOOTNOTE_OF` | Footnote linked to table / fact |
| `REFERENCES` | Cross-links where modeled |
| `TEMPORAL_TRANSITION` | Links filings on a timeline (e.g. FY2023 10-K → FY2024 10-K) |

Exports: **GraphML** + manifest—not an opaque vector DB.

**Visual:** Small graph fragment with edge labels; link to interactive viz.

**Speaker notes (~2 min)**

**`CONTAINS`** — The workhorse edge. Document → section → chunk hierarchy. Micro extraction walks **`CONTAINS`** to collect candidate evidence inside a meso-selected section. Every hop in **`graph_traversal`** in the trajectory JSON should be explainable as structural containment.

**`NEXT`** — Reading order within a section—useful when prose spans multiple paragraph chunks and order matters for synthesis.

**`FOOTNOTE_OF`** — Links footnote chunks to table or fact nodes—critical when the answer is “see Note 5” or when numeric cells have explanatory footnotes. Agent collects these when traversing table regions.

**`REFERENCES`** — Cross-links where modeled (internal references between sections or exhibits).

**`TEMPORAL_TRANSITION`** — Connects filings on a timeline across the issuer corpus—e.g. FY2023 10-K document node → FY2024 10-K. FinAgentBench-style comparison questions should traverse **two document subtrees** linked by time, not one bag of chunks.

**Why GraphML + manifest, not a black-box DB:** FINOS and model-risk audiences can **open the file**, diff snapshots across releases, and verify which accessions were in scope. Vector stores alone do not expose filing boundaries cleanly.

**Optional semantic edges:** Config supports `SEMANTIC_SIMILARITY` edges but they are **off by default**—we prioritize auditable structure over embedding shortcuts in CI and paper repro.

**Demo cue:** Open the [interactive AAPL eval graph](https://caldeirav.github.io/agentic-graphrag-finance/assets/aapl-eval-graph/visualization.html?v=2)—zoom from DOCUMENT to a single XBRL fact; show edge labels if the viz supports it.

**Transition:** “Three benchmark families, three paths through this same graph—that is the intuition for our eval set.”

---

### Slide 14 — Three benchmark styles, three graph paths (motivating example)

**On-slide content**

| Style | Example question | Graph path |
|-------|------------------|------------|
| **FinanceBench** | What was total net sales in the most recent fiscal year? | FY2024 10-K → Item 7 / XBRL net-sales fact |
| **FinDER** | What risk factors for supply chain? | FY2024 10-K → Item 1A narrative |
| **FinAgentBench** | Compare net sales discussion across two 10-Ks | Two DOCUMENT nodes → Item 7 + `TEMPORAL_TRANSITION` |

**Note:** Demo corpus uses **frozen** FY2023/FY2024 Apple 10-K accessions for reproducibility—not live “as of today” EDGAR.

**Visual:** Screenshot from interactive graph with three highlighted paths (matches `eval_context.md` item IDs).

**Speaker notes (~3 min)**

**Use this slide to connect benchmarks to graph topology** before you show agent code. Same issuer (Apple), same graph, three different **navigation paths**:

1. **FinanceBench-style — numeric lookup:** “What was total net sales in the most recent fiscal year?” Path: FY2024 **10-K DOCUMENT** → **XBRL facts section** (or Item 7 where narrative also discusses sales) → **`CHUNK_XBRL_FACT`** for `RevenueFromContractWithCustomerExcludingAssessedTax`. Macro binds **one** annual filing; intent is numeric; meso hits **`xbrl_bucket`**; micro ranks the revenue concept for the latest fiscal period.

2. **FinDER-style — narrative retrieval:** “What risk factors does the company highlight for supply chain?” Path: same filing → **Item 1A** (`risk_factors`) → **`CHUNK_PARAGRAPH`** nodes containing supply-chain language. Intent is qualitative; meso must **not** stop at XBRL bucket for this question—demonstrates why stratified eval by evidence type matters.

3. **FinAgentBench-style — multi-filing comparison:** “Compare net sales discussion across the two most recent 10-K filings.” Path: **two DOCUMENT nodes** → Item 7 (or XBRL + MD&A) on each → linked by **`TEMPORAL_TRANSITION`**. Macro must bind **two accessions** before meso/micro run. Flat RAG often retrieves chunks from one filing only and still produces a fluent comparison—graph grounding makes that failure visible in **`routing_decisions`** judge scores.

**Frozen corpus caveat (say explicitly):** The public demo graph pins **FY2023/FY2024** Apple 10-K accessions for reproducible CI and paper baselines—not “whatever is latest on EDGAR today.” Live `ask` on a freshly materialized corpus may bind FY2025/FY2024. Both are correct relative to their snapshot—what matters is **manifest alignment** between question, graph, and eval item.

**CI item IDs** if anyone inspects the repo: `0.0.0-financebench-001`, `0.0.0-finder-001`, `0.0.0-finagentbench-001` — see [eval_context.md](assets/aapl-eval-graph/eval_context.md).

**Transition:** “Navigation is implemented as a five-stage LangGraph workflow—not one retrieval call.”

---

### Slide 15 — Multi-stage agentic retrieval (not one vector search)

**On-slide content**

| Stage | Decides |
|-------|---------|
| **Macro routing** | Which accession(s) and temporal anchor (10-K vs 10-Q, YoY pair) |
| **Intent routing** | Numeric vs qualitative; comparison vs point lookup |
| **Meso routing** | Which sections (TOC planner, section scoring, graph walk) |
| **Micro extraction** | Which chunks / XBRL facts inside sections |
| **Synthesis** | Grounded answer with **ordered citations**; numeric guards |

**Visual:** LangGraph state diagram (macro → intent → meso → micro → synthesize).

**Speaker notes (~2 min)**

**Contrast explicitly with “RAG = embed + top-k”:** Our agent makes **sequential decisions**, each logged. The graph is the shared substrate; stages differ in **which nodes they read** and **what they write** to the trajectory.

**Stage-by-stage one-liner (expand the table):**

- **Macro routing** — Resolves **scope**: which accession(s), which temporal anchor (latest annual, prior quarter, YoY pair). Uses manifest metadata, not chunk text. Failure here invalidates the entire answer regardless of retrieval quality.

- **Intent routing** — Classifies **information need**: numeric vs qualitative; point lookup vs comparison. Sets biases like `xbrl_primary` vs narrative emphasis—steers meso/micro without hard-coded rules for every question template.

- **Meso routing** — **Section selection**: TOC planner builds a table of contents from SECTION nodes; LLM ranks section IDs; graph walk toward MD&A, risk, XBRL bucket, footnotes. This is the core **graph walk** vs flat retrieval.

- **Micro extraction** — **Evidence ranking** inside chosen sections: collect chunks under `CONTAINS`, score XBRL facts by concept match, attach excerpts and content hashes.

- **Synthesis** — **Answer generation** with **ordered citations** to chunk IDs; guards against ungrounded numerics, weak comparison support, citing evidence not in the prompt.

**Implementation:** LangGraph state machine in `src/retrieval/orchestration/graph.py`; local LLM via **LM Studio** (OpenAI-compatible API); configs in `configs/lm_studio.yaml`, `configs/graph_navigation.yaml`.

**Analyst mirror:** Macro/meso/micro map to “which filing, which section, which line item”; intent + synthesis map question understanding to answer form.

**Transition:** “We will trace one FinAgentBench-style question end to end: year-over-year net sales.”

**External references**

- LangGraph: [langchain-ai/langgraph](https://github.com/langchain-ai/langgraph)

---

### Slide 16 — **Drill-down:** Agent demo setup (the example question)

**On-slide content**

**Question (FinAgentBench-style YoY):**

> How did total net sales change year over year?

**Commands:**

```bash
uv run agent-query materialize --ticker AAPL
uv run agent-query ask --ticker AAPL --trace verbose \
  --query "How did total net sales change year over year?"
```

**What to watch:** macro binding (two 10-Ks) → intent `numeric` → meso `xbrl_bucket` → micro revenue facts → cited synthesis.

**Visual:** Terminal mock or MLflow screenshot placeholder.

**Speaker notes (~2 min)**

**Why this question:** “How did total net sales change year over year?” is richer than a single-filing lookup—it forces **macro comparison binding**, **numeric intent**, **XBRL meso routing on two filings**, and **synthesis with two cited facts**. It is the canonical example in [end-to-end-walkthrough.md](end-to-end-walkthrough.md).

**Read the question aloud** and ask the audience what they would do manually: (1) get latest two **annual** 10-Ks, (2) find net sales / revenue for each fiscal year, (3) compute change. The agent stages map 1:1 to that workflow.

**Commands:** Show on slide; optionally run live if LM Studio + `.env` are ready. `--trace verbose` prints Rich panels to **stderr**—answer on stdout, trace on stderr—so demos stay readable.

**Set expectations for live vs frozen corpus:** On a freshly materialized AAPL corpus, macro may bind **FY2025 and FY2024** 10-K accessions (`...-25-000079`, `...-24-000123`). Paper benchmark items may pin **FY2024/FY2023**. Call out which snapshot you are using so judge/eval dates do not confuse the room.

**“What to watch” checklist** (narrate during demo):
1. Macro trace — two accessions, `comparison_mode: YoY`
2. Intent — `numeric`, `source_bias: xbrl_primary`
3. Meso — `toc_planner` selects **`xbrl_bucket`** on **both** filings
4. Micro — two `CHUNK_XBRL_FACT` nodes with revenue concept and distinct periods
5. Synthesis — dollar amounts, fiscal labels, taxonomy concept name, citations

**If live demo fails:** Fall back to walkthrough trace excerpts or pre-captured MLflow run—Appendix B.

**Transition:** “Stages one and two decide scope and question type before any evidence is read.”

---

### Slide 17 — Stage 1–2: Macro + intent routing

**On-slide content**

**Macro (which filings?)**

- LLM proposes YoY comparison on latest two **annual 10-Ks**
- Deterministic validator checks accessions exist in corpus manifest
- Example trace: `selected_accessions: ['...-25-000079', '...-24-000123']`, `comparison_mode: YoY`

**Intent (what kind of answer?)**

- Classifies **`numeric`** → `source_bias: xbrl_primary`
- Query text only; logged as `intent_router.json`

**Visual:** Split panel: manifest metadata on left; intent label on right.

**Speaker notes (~3 min)**

**Macro routing — what happens under the hood:**

The LLM reads the natural-language query and proposes a **binding**: which accession(s) in the corpus snapshot, comparison mode (here **YoY**), fiscal period labels. Crucially, at this stage the system uses **`GraphSnapshot` manifest** fields—`form_type`, `period_end`, `filed_at`—not XBRL fact values. That prevents a subtle bug: retrieving a revenue number before you have confirmed **which filing** it must come from.

A **deterministic validator** (`src/retrieval/macro/validator.py`) then checks: proposed accessions exist in the manifest; comparison queries have the expected arity; temporal anchor is coherent. If validation fails, the workflow can short-circuit to synthesis with an abstention or error—better than a confident wrong filing.

**Example trace to narrate:** `selected_accessions: ['0000320193-25-000079', '0000320193-24-000123']`, `comparison_mode: YoY`, `period_labels: FY2025, FY2024`.

**Operator overrides:** `--anchor prior-quarter` or explicit period flags for testing; benchmark **`ablation-no-macro`** skips free-form macro by pre-binding accessions from item metadata—isolates how much macro matters when bindings are given.

**Intent routing — why a separate stage:**

Query text alone drives classification: here **`numeric`** because the question asks for how sales **changed**—magnitude/direction—with implied quantities. That sets **`source_bias: xbrl_primary`** so meso prefers **`xbrl_bucket`** over MD&A prose. A FinDER-style risk question on the same filing would classify **`qualitative`** and route meso toward **Item 1A** instead—same macro binding, different intent outcome.

Intent output is stored in **`intent_trace`** / `intent_router.json` in MLflow—auditors can verify the router did not silently use the wrong evidence family.

**Failure mode to mention:** Macro mis-binding (e.g. two 10-Qs instead of two 10-Ks for YoY) produces coherent-sounding answers with wrong economics—structural metrics like **accession binding accuracy** exist precisely to catch this.

**Transition:** “Given the right filings and numeric intent, meso opens the right sections.”

---

### Slide 18 — Stage 3: Meso routing (section selection)

**On-slide content**

- **TOC planner** builds table of contents from SECTION nodes (`narrative_kind`: `xbrl_bucket`, `md_and_a`, `risk_factors`, …)
- LLM ranks section node IDs per bound filing
- YoY net sales → top sections: **`xbrl_bucket`** on each 10-K—not Item 1A risk factors

Example trace:

```text
toc_planner (xbrl_bucket): 2 section(s)
  doc-...-25-000079-xbrl-facts
  doc-...-24-000123-xbrl-facts
```

**Visual:** SECTION list with `xbrl_bucket` highlighted for both filings.

**Speaker notes (~3 min)**

**Meso is section selection**—the bridge between “right filing” and “right evidence.” Default mode: **TOC planner** (`configs/graph_navigation.yaml` → `meso.discovery_mode: toc_planner`).

**Mechanism:**
1. For each macro-bound filing, collect **SECTION** nodes into a table of contents—labels, slugs, **`narrative_kind`** tags: `xbrl_bucket`, `md_and_a`, `risk_factors`, etc.
2. LLM ranks **section node IDs** given the query and intent bias—not free-text section names that might hallucinate.
3. Graph walk expands from chosen sections toward candidate chunk subtrees.

**YoY net sales trace:** Both filings → top sections are **`xbrl_bucket`** (`doc-...-xbrl-facts`), **not** Item 1A risk factors—even though risk text might mention “sales exposure.” TOC prompts explicitly steer numeric revenue questions away from narrative risk sections.

**Contrast on the same slide (important pedagogical point):** FinDER-style “supply chain risk factors” on the **same Apple filing** should meso-route to **Item 1A** paragraph chunks. Show that one graph supports multiple QA regimes via **intent + meso**, not separate indexes per benchmark.

**vs flat-chunk RAG:** Dense retrieval returns top-k chunks **globally** across the filing—often MD&A prose mentioning revenue instead of the tagged XBRL fact. Meso enforces **regulatory structure first**, micro ranks within that scope.

**Config knob:** `toc_planner` vs other discovery modes in `graph_navigation.yaml`—mention only if audience is implementers.

**Transition:** “Inside the XBRL bucket, micro finds the exact facts.”

---

### Slide 19 — Stage 4: Micro extraction (evidence ranking)

**On-slide content**

- Walker collects chunk IDs under `CONTAINS` (+ `FOOTNOTE_OF` when relevant)
- For XBRL bucket + financial query: narrow to concepts matching query (revenue / net sales) via `xbrl_concept` on `CHUNK_XBRL_FACT`
- Each **EvidenceChunk** carries: `excerpt`, `accession`, `section_id`, `content_hash`, navigation path

Example evidence (abbreviated):

| Score | Node | Content |
|-------|------|---------|
| 46.5 | `...-25-000079-xbrl-f31f...` | FY2025 revenue fact |
| 46.5 | `...-24-000123-xbrl-f31f...` | FY2024 revenue fact |

**Visual:** Two fact nodes side-by-side with formatted excerpts.

**Speaker notes (~3 min)**

**Micro collects and ranks evidence** inside meso-selected sections.

**Collection:** Walker follows **`CONTAINS`** edges from section nodes to chunk nodes; when tables are in scope, **`FOOTNOTE_OF`** brings linked footnotes. Each candidate becomes an **`EvidenceChunk`** with:
- **`excerpt`** — human-readable text (for XBRL, the `fact_to_excerpt` string)
- **`accession`**, **`section_id`**, **`content_hash`** — reproducibility and validator checks
- Navigation path — chain of node IDs the agent traversed

**XBRL narrowing:** For financial queries in **`xbrl_bucket`**, do not score all thousands of facts equally—filter/rank by **`xbrl_concept`** matching query semantics (revenue, net sales, assets, etc.) using helpers in `src/parsing/xbrl_facts.py`.

**Walk the example table:** Two facts, equal scores (~46.5), different accessions/periods—FY2025 vs FY2024 revenue. That pair is exactly what YoY synthesis needs. If micro returned only one period, synthesis should abstain or judge flags **`synthesis_grounding`**.

**Decimals reminder:** Excerpts show **$391.04 billion** because `format_xbrl_numeric()` applied SEC scaling—if you show raw XML integers without formatting, LLMs and judges misread magnitude.

**Evaluation link:** Benchmark **relevance labels** are sets of chunk IDs deemed sufficient for an item. **MRR / nDCG@10** compare the **ordered citations in the final answer** to those labels—not internal ranker scores alone. Strong micro + weak synthesis still yields high MRR; that is the “synthesis gap” story on Slide 22.

**Transition:** “Synthesis turns those excerpts into a cited natural-language answer.”

---

### Slide 20 — Stage 5: Synthesis (grounded answer)

**On-slide content**

Example answer (from walkthrough):

```text
Total net sales increased year over year, from $391.04 billion in FY2024 to
$416.16 billion in FY2025 (+$25.12 billion, +6.4%), per
RevenueFromContractWithCustomerExcludingAssessedTax in the bound 10-K filings.
```

Rules: use **only** retrieved excerpts; name fiscal periods; ordered citations to chunk IDs.

**Visual:** Answer with citation callouts mapped to graph node IDs.

**Speaker notes (~3 min)**

**Read the example answer slowly** and point at each grounding element:
- Direction (**increased**)
- Both period values (**$391.04B FY2024**, **$416.16B FY2025**)
- Delta (**+$25.12B**, **+6.4%**)
- Taxonomy anchor (**RevenueFromContractWithCustomerExcludingAssessedTax**)
- Scope (**bound 10-K filings**—not model priors)

**Synthesis prompt rules (conceptual):** Use **only** provided excerpts; cite **chunk IDs in retrieval order**; name fiscal periods explicitly; do not invent numbers not present in evidence.

**Guards (why synthesis is not “just ask GPT”):** Additional logic targets known finance QA failure modes—ungrounded numerics, comparison answers without evidence from **both** filings, mismatch between XBRL concept cited and narrative wording. These guards are where active engineering continues.

**Honest research status:** On the frozen 200-item dev split, **graph-full** shows **MRR ≈ 0.916** but **task_success ≈ 0.467** (value alignment). Interpretation: **retrieval and citation ranking often succeed** while **answer wording, narrative items, or comparison synthesis** still fail judge scrutiny—especially FinDER-style and complex FinAgentBench items. Do not oversell; point to Slide 26.

**Config:** Evidence budget and model settings in `configs/lm_studio.yaml`—context length must fit macro + meso traces + top-k excerpts.

**Transition:** “The answer string is not the only output—we export the full trajectory for external judging.”

---

### Slide 21 — Trajectory logging and external judge (FINOS-relevant evaluation)

**On-slide content**

**`agent_trajectory.json` captures:**

- `plan` — macro intent, binding steps
- `document_route` — bound accessions, fiscal labels
- `graph_traversal` — meso/micro hops (section + chunk IDs)
- `evidence` — what reached synthesis prompt

**Gemini judge (when validation = complete):**

| Criterion | Question |
|-----------|----------|
| `trajectory_coherence` | Plan → route → hops → evidence consistent? |
| `routing_decisions` | Right filings and sections? |
| `retrieval_fidelity` | Evidence matches question? |
| `synthesis_grounding` | Answer supported by excerpts? |

**Visual:** Sequence diagram: LangGraph → validator → judge → MLflow.

**Speaker notes (~3 min)**

**Why trajectories matter for FINOS / regulated AI:** A final answer string is insufficient for audit. Reviewers ask: **Which filing did you use? Which sections did you read? Which chunks supported each claim?** Our **`agent_trajectory.json`** is designed to answer those questions in machine-readable form.

**Walk each trajectory field:**

- **`plan`** — Macro intent, binding steps, LLM rationale (structured, not chain-of-thought essay). Shows *why* two 10-Ks were chosen for YoY.

- **`document_route`** — Bound accessions, `filed_at`, fiscal labels—ground truth for “was the right filing in scope?”

- **`graph_traversal`** — Meso/micro hops: section and chunk node IDs, edge types (`CONTAINS`). This is the **reasoning trajectory** the session abstract advertised.

- **`evidence`** — Which chunk IDs were retrieved vs which actually entered the synthesis prompt—detects ranking/synthesis disconnects.

**Validator gate (`validate_trajectory`):** Checks schema, content hashes, accession consistency between route and hops. Status **`complete`** → judge runs; **`incomplete`** or **`non_reproducible`** → **`not_evaluable`** (no headline score—prevents judging broken traces).

**Gemini judge (four criteria)—explain each in plain language:**

| Criterion | Speaker phrasing |
|-----------|------------------|
| `trajectory_coherence` | “Does the story hang together from plan to evidence?” |
| `routing_decisions` | “Were the right filings and sections chosen for this question?” |
| `retrieval_fidelity` | “Does the retrieved evidence match the question and bindings?” |
| `synthesis_grounding` | “Is every claim in the answer supported by cited excerpts?” |

**Separate outcome vs process:** **Value alignment** (task_success) scores answer vs human GT; **trajectory fidelity** scores navigation quality. They can diverge—use both in FINOS benchmarking discussions.

**Demo path:** `uv run mlflow ui --backend-store-uri sqlite:///mlflow.db` → latest `ask` run → artifacts **`agent_trajectory.json`**, **`evaluation/judge_verdict.json`**, per-criterion scores on stderr with `--trace normal`.

**Configs:** `configs/judges/gemini_2_5_pro.yaml` (model pin, temperature 0), `configs/trajectory_judge.yaml`.

**Transition:** “Those judge scores feed headline tables—but do not collapse retrieval metrics and outcome metrics into one number.”

---

### Slide 22 — Metrics: retrieval vs outcome (do not collapse them)

**On-slide content**

| Category | Metrics | What they tell you |
|----------|---------|-------------------|
| **Outcome** | `task_success` (mean value alignment, n=200) | Did the answer match GT? |
| **Retrieval ranking** | MRR, MAP, nDCG@10 vs relevance labels | Did citations hit labeled chunks? |
| **Process** | Trajectory fidelity | Was navigation sensible? |
| **Structural** | Accession binding accuracy, section-path hit rate | Macro/meso audit |

**Baseline (graph-full, paper-v1.0 lock):** `task_success` ≈ **0.467** · `mrr` ≈ **0.916** · `nDCG@10` ≈ **0.631**

**Visual:** Two-bar chart metaphor: tall MRR bar, moderate task_success bar—label “synthesis gap.”

**Speaker notes (~3 min)**

**This slide is a FINOS headline—slow down.**

**Four metric categories (table):**

1. **Outcome — `task_success`:** Mean **value alignment** over **n=200** dev items (v2.0.0). Single judge criterion; missing scores count as **0**. Answers “did we get the right answer vs human ground truth?” **Baseline graph-full ≈ 0.467**—moderate, not solved.

2. **Retrieval ranking — MRR, MAP, nDCG@10:** Compare **ordered citation list** in the agent answer to graph-grounded **relevance labels** per item. Answers “did we cite the right chunks?” **Baseline MRR ≈ 0.916**—very strong. **nDCG@10 ≈ 0.631**.

3. **Process — trajectory fidelity:** Judge rubric on navigation quality—complements task_success when answer is wrong but route was sensible (or vice versa).

4. **Structural — accession binding accuracy, section-path hit rate:** Audit macro/meso alignment with **`expected_bindings`** in benchmark items—critical for FinAgentBench-style tasks.

**The synthesis gap (spell it out):** High MRR + moderate task_success means the system often **finds and cites** the right evidence but still **words the answer wrong**, omits required comparison claims, or fails narrative items. If you only report retrieval metrics, you **overstate** system readiness; if you only report task_success, you **hide** retrieval improvements from ablations.

**Ranking metric detail:** Computed from **final answer citations**, not hidden ranker internals—so improving synthesis order affects MRR too.

**Reproducibility:** After `repro run-all`, **`repro verify-tables`** checks exported CSVs against **`releases/paper-v1.0/expected_checksums.json`**—ranking metrics must match exactly; task_success allows ±0.02 tolerance.

**Transition:** “Those 200 items are not imported from FinanceBench—we generate them natively on frozen graphs.”

**Sources:** [research-reproduction.md](research-reproduction.md), [research-proposal.md § Metrics](research-proposal.md#metrics).

---

### Slide 23 — **Drill-down:** Native benchmark generation (custom-judge v2.0.0)

**On-slide content**

**We do not import FinDER/FinanceBench/FinAgentBench rows.**

Pipeline:

```text
Sampling → Materialize (same as production) → Gemini item authoring → Validate + dedup
  → dev_pool.jsonl → profile-balanced dev.jsonl (200) → publish → offline repro
```

Published bundle: `data/benchmarks/custom-judge/v2.0.0/` · Release lock: `releases/paper-v1.0/manifest.yaml`

**Visual:** Generation flowchart from [custom-judge-dataset-generation.md](custom-judge-dataset-generation.md).

**Speaker notes (~3 min)**

**Lead with the negative:** We **do not bulk-import** FinanceBench, FinDER, or FinAgentBench rows. Reasons: PDF/page bindings do not transfer to our graphs; third-party corpora drift; FINOS-grade repro needs **frozen hashes** of filings, items, and relevance labels.

**Walk the pipeline left to right:**

1. **Sampling** — Deterministic draw from **20-ticker allowlist** (`configs/benchmarks/issuer_allowlist_v1.json`); seed + filters → **`sampling_manifest.json`** with content hashes.

2. **Materialize** — Same **`run_materialize_pipeline`** as production `materialize`—not a shortcut parser. Graphs copied into draft **`corpus/`** tree; **`graph_node_index.json`** lists every valid `{accession}/{section_slug}`.

3. **Gemini item authoring** — Profile-specific prompts (`configs/benchmarks/inspiration_profiles/*.yaml`) generate question, answer, **`expected_bindings`**, **`expected_section_paths`**, **`required_claims`** (v2).

4. **Validate + dedup** — Reject hallucinated paths, single-filing FinAgentBench items, empty answers, near-duplicate questions. Accepted pool → **`dev_pool.jsonl`**.

5. **Profile-balanced selection** — Largest-remainder quotas → **`dev.jsonl` (200 items)** — e.g. 68 / 66 / 66 across profiles.

6. **Publish + offline repro** — Operator sign-off gates; bundle at **`data/benchmarks/custom-judge/v2.0.0/`**; paper lock **`releases/paper-v1.0/manifest.yaml`**.

**Two-phase eval culture (FINOS):**
- **Phase 1 (generate):** Live EDGAR + Gemini—expensive, infrequent.
- **Phase 2 (`repro run-all`):** **`OFFLINE_BENCHMARK=1`** — no EDGAR during scoring; all five variants see **identical** corpus bytes.

**CLI:** `uv run agent-query benchmark-dataset generate` → `publish` · `uv run agent-query repro run-all --manifest releases/paper-v1.0/manifest.yaml --defer-judge`

**Transition:** “Each inspiration profile encodes different binding rules and ground-truth shape.”

**Guide:** [custom-judge-dataset-generation.md](custom-judge-dataset-generation.md).

---

### Slide 24 — Inspiration profiles and grounding rules

**On-slide content**

| Profile | Upstream | Binding rules | v2 ground truth |
|---------|----------|---------------|-----------------|
| `financebench` | FinanceBench | Single filing; graph-resolvable section paths | Short numeric/text `answer` |
| `finder` | FinDER | Narrative retrieval focus | `answer` + `required_claims` |
| `finagentbench` | FinAgentBench | **≥2 accessions** | `comparison_structured` + per-filing & cross-filing claims |

**Dev split (v2.0.0):** 200 items · ~68 / 66 / 66 profile quota · ≥40 multi-filing · 100% non-empty `ground_truth.answer`

**Visual:** Table with one example question per profile (from AAPL eval context).

**Speaker notes (~3 min)**

**Three profiles = three stress tests** for the same graph stack:

**`financebench` (single-filing, numeric/text):** Mimics FinanceBench taxonomy—metrics-generated, domain-relevant questions. Ground truth is a concise **`ground_truth.answer`**. Must bind to **`expected_section_paths`** resolvable in **`graph_node_index.json`**—we use section slugs, not PDF page numbers. Example: net sales in latest fiscal year → XBRL fact path under FY2024 10-K.

**`finder` (single-filing, narrative):** Mimics FinDER retrieval difficulty—ambiguous wording, evidence in prose. v2 requires **`answer` + `required_claims`** so headline **`task_success`** uses one value-alignment path for all 200 items (no rubric-only half of the dataset).

**`finagentbench` (multi-filing, comparison):** Mimics FinAgentBench agentic scope—**≥2 accessions** per item, **`comparison_structured`** answers with **per-filing atomic claims** plus a **cross-filing synthesis claim** (e.g. “both filings discuss net sales in Item 7; FY2024 grew vs FY2023”). v2 enforces **≥40 multi-filing items** in the dev split so macro routing is exercised, not optional.

**Validation failures to mention (shows rigor):**
- **`unknown_section_path`** — Gemini invented a section not in the graph index.
- **`finagentbench_requires_multi_filing`** — only one accession bound.
- **`missing_ground_truth` / `required_claims`** — v2 answer-GT gates.
- **Dedup** — near-duplicate questions rejected by similarity threshold.

**Publish gates (v2):** `answer_gt_coverage` = 1.0, `multi_filing_count` ≥ 40, `macro_bindability_failures` = 0, operator **`--publish-signoff`**.

**Point to AAPL eval examples** on slide—tie back to Slide 14 paths.

**Transition:** “We run five system variants on those 200 items to isolate what structure buys us.”

---

### Slide 25 — Experimental variants (what we compare)

**On-slide content**

| Variant | Change | Research question |
|---------|--------|-------------------|
| **graph-full** | Full pipeline | Baseline |
| **flat-chunk** | MiniLM dense retrieval; no graph walk | How much does structure add vs strong flat RAG? |
| **ablation-no-macro** | Pre-bound filings | Value of free-form filing selection? |
| **ablation-no-walker** | No meso/micro hops | Can intent + synthesis replace section traversal? |
| **ablation-xbrl-only** | Drop HTML narrative chunks | Dependence on prose vs tagged facts? |

**Stratify by evidence source:** HTML vs XBRL vs mixed—pooled scores mislead when ablations cannot reach narrative.

**Visual:** Five-row table; optional small bar chart from `by_evidence_source.csv` if repro report available.

**Speaker notes (~2 min)**

**Each variant removes one architectural commitment** while keeping the same 200 items and frozen corpus—fair ablation design.

**`graph-full`:** Production baseline—all stages, all chunk types (HTML + XBRL).

**`flat-chunk`:** **MiniLM** dense retrieval over the **same chunk set**—no graph walk. Strong non-graph baseline; answers “how much does explicit navigation add over good embeddings?” Preliminary pattern: competitive on some ranking metrics, **lags task_success** when macro/section fidelity matters.

**`ablation-no-macro`:** Filings **pre-bound** from item metadata—tests free-form filing selection vs given bindings. Occasionally pools odd outcomes; use item-level drill-down before over-interpreting small deltas.

**`ablation-no-walker`:** Removes meso/micro graph hops—intent + synthesis only over a degraded retrieval path. Near-zero on **HTML-stratified** items because narrative chunks are unreachable.

**`ablation-xbrl-only`:** Drops HTML narrative chunks—isolates dependence on prose vs tagged facts. Fails FinDER-style items by construction.

**Stratification mandate (FINOS):** Report **`by_evidence_source.csv`** — HTML vs XBRL vs mixed. Pooled leaderboard scores **lie** when an ablation structurally cannot retrieve a stratum.

**Repro command:** `uv run agent-query repro run-all --manifest releases/paper-v1.0/manifest.yaml --defer-judge --output reports/repro-paper-v1.0`

**Optional:** Show **`repro report` HTML**—item-first investigation, not only aggregate tables.

**Transition:** “Numbers are preliminary—here is what we think they mean so far.”

---

### Slide 26 — Preliminary observations (honest research status)

**On-slide content**

Hypotheses under active investigation—not final claims:

- **Retrieval vs outcome gap** — high MRR, moderate task_success → synthesis/grounding is the error mode on narrative items.
- **Flat baseline** — competitive on some ranking metrics; lags task_success when filing scope + section fidelity matter.
- **Ablation asymmetry** — variants that cannot reach HTML fail HTML-stratified items entirely (expected; must stratify).
- **Architecture** still iterating on comparison answers and multi-filing synthesis.

**Visual:** “Research in progress” footer; link to GitHub issues / repro report.

**Speaker notes (~2 min)**

**Set tone:** These are **hypotheses under investigation**, not vendor claims. Align with [research-proposal.md](research-proposal.md) disclaimer—methodology doc, conclusions still iterating.

**Observation 1 — Retrieval vs outcome gap:** Graph-full achieves **high MRR (~0.916)** with **moderate task_success (~0.467)**. Working theory: **synthesis, comparison wording, and narrative grounding** dominate errors—not “retrieval is broken.” Implication for roadmap: invest in synthesis guards and comparison templates while preserving graph navigation.

**Observation 2 — Flat baseline asymmetry:** MiniLM flat-chunk remains **competitive on ranking** for some item types but **underperforms on task_success** when questions require correct **filing scope** and **section fidelity**—consistent with why macro/meso exist.

**Observation 3 — Ablation asymmetry:** Variants that cannot reach HTML narrative show **~zero** on HTML-stratified items—expected, but **pooled aggregates hide this**. Always stratify in FINOS benchmark reports.

**Observation 4 — Active engineering:** Multi-filing **comparison synthesis** and FinAgentBench-style **`required_claims`** matching still being hardened—architecture makes failures **visible** in trajectories even when headline accuracy is mid-range.

**Open questions (optional Q&A seed):**
- Error attribution: macro vs meso vs micro vs synthesis?
- Minimum graph schema richness to beat flat RAG at fixed citation budget?
- Scoring partial credit when per-filing evidence is right but cross-filing synthesis is wrong?

**Point to `repro report` HTML** for item-level forensics—not leaderboard-only culture.

**Transition:** “If you take one builder checklist away from Docling…”

---

### Slide 27 — Takeaways for developers building on Docling

**On-slide content**

1. **Do not treat filings as flat text** — invest in typed graphs when structure exists (XBRL, sections, tables).
2. **Use docling-graph as a contract** — deterministic mapping for tagged SEC data beats LLM re-extraction every filing.
3. **Stage your agent; log trajectories** — know which stage broke (macro / meso / micro / synthesis).
4. **Measure retrieval and outcome separately** — both are necessary for financial QA.
5. **Open stack + enterprise path** — Docling, docling-graph, LangGraph, LM Studio locally; Red Hat AI on OpenShift AI for managed scale.

**Visual:** Numbered list; Docling + FINOS logos.

**Speaker notes (~2 min)**

**Deliver each takeaway as an actionable decision**, not slogans:

1. **Do not treat filings as flat text.** If your source has XBRL tags, section Items, and tables, build a **typed graph first**—then optionally add embeddings as a secondary signal. Path-finding through `CONTAINS` is interpretable; cosine similarity alone is not.

2. **Use docling-graph as a contract.** For tagged SEC data, **`Docling → deterministic mapper → GraphSnapshot`** is faster, cheaper, and more auditable than running LLM graph extraction on every filing. Use upstream **`docling-graph convert`** when structure is implicit (PDFs), not when XBRL already encodes it.

3. **Stage your agent; log trajectories.** When an answer fails, you need to know **which stage broke**—macro bound the wrong 10-Q, meso opened Item 1A instead of XBRL bucket, micro missed the fact, synthesis hallucinated a delta. One blended “retrieval score” cannot tell you that.

4. **Measure retrieval and outcome separately.** Report **MRR/nDCG** and **task_success** side by side. FINOS evaluations should resist collapsing them into a single “accuracy” number.

5. **Open stack + enterprise path.** Run locally: Docling, docling-graph schema, LangGraph, LM Studio. Scale in enterprise: same Docling in **Red Hat AI / OpenShift AI** pipelines—no proprietary parser lock-in.

**FINOS governance angle:** Artifacts you can attach to a model card or audit packet—**GraphML**, **`agent_trajectory.json`**, **frozen corpus hashes**, **`expected_checksums.json`**.

**Transition:** “Here is the full blueprint on one slide.”

---

### Slide 28 — Blueprint: verifiable high-precision retrieval architecture

**On-slide content**

```text
┌─────────────┐   ┌──────────────┐   ┌─────────────────┐   ┌──────────────┐
│ EDGAR XBRL  │ → │ Docling parse │ → │ GraphSnapshot   │ → │ Staged agent │
└─────────────┘   └──────────────┘   │ (GraphML+audit) │   │ + citations  │
                                      └────────┬────────┘   └──────┬───────┘
                                               │                    │
                                      ┌────────▼────────┐   ┌───────▼────────┐
                                      │ Native benchmark │   │ Trajectory     │
                                      │ (200 items,      │   │ judge + MLflow │
                                      │  frozen corpus)  │   └────────────────┘
                                      └─────────────────┘
```

**Get started:**

```bash
git clone https://github.com/caldeirav/agentic-graphrag-finance
uv sync --locked && cp .env.example .env
uv run agent-query materialize --ticker AAPL
uv run agent-query ask --ticker AAPL --trace normal --query "..."
```

**Visual:** Architecture blueprint + QR code to repo and interactive graph.

**Speaker notes (~2 min)**

**Close the narrative arc** from Slide 1: standardized XBRL existed; we added **graph preservation**, **staged navigation**, and **trajectory-based evaluation** so AI systems can be tested and audited like other regulated pipelines.

**Walk the ASCII blueprint bottom row:** Native benchmark (200 items, frozen corpus) and trajectory judge are **peers** of the agent—not afterthoughts. Evaluation is built into the architecture, which is what FINOS AI Evaluation and Benchmarking cares about.

**Get-started commands:** Read slowly for note-takers—clone, `uv sync`, configure `.env` (`SEC_EDGAR_USER_AGENT`, `GOOGLE_API_KEY`), start LM Studio, `materialize`, `ask`. Emphasize **open source** and that interactive path takes one GPU-class local model + Gemini judge API for audit.

**Reproducibility culture:** Mention **`repro verify-corpus`** and **`repro verify-tables`** against **`releases/paper-v1.0/expected_checksums.json`**—challenge other teams to match hashes, not hand-wavy “we beat RAG.”

**Collaboration invite:** Benchmark authoring, synthesis guards, new inspiration profiles (e.g. footnote-heavy items, segment reporting), docling-graph viz improvements.

**QR codes / links:** Repo + interactive AAPL graph—let people explore during Q&A.

**Transition:** “Resources and backup answers for Q&A.”

---

### Slide 29 — Q&A / resources

**On-slide content**

**Docs**

- [End-to-end walkthrough](end-to-end-walkthrough.md)
- [Custom-judge dataset generation](custom-judge-dataset-generation.md)
- [Research reproduction](research-reproduction.md)
- [Research proposal](research-proposal.md)

**External**

- [Docling XBRL conversion](https://docling-project.github.io/docling/examples/xbrl_conversion/)
- [docling-graph](https://github.com/docling-project/docling-graph)
- FinanceBench · FinDER · FinAgentBench papers (arXiv links)

**Visual:** QR codes + short link list.

**Speaker notes (~remaining time)**

**Prepared answers for common questions:**

| Question | Suggested answer |
|----------|------------------|
| **Cost?** | Ingest/materialize is CPU + EDGAR rate limits; agent runs on **local LM Studio** (your hardware); judge uses **Gemini API** per query/item—benchmark repro batches judge with **`--defer-judge`**. |
| **Latency?** | Multi-stage agent is **slower than single-shot RAG**—five LLM calls + graph walks—but each stage is bounded and loggable; trade latency for auditability. |
| **Coverage?** | US **10-K / 10-Q** English XBRL; not mutual funds, not live market data, not multilingual yet. |
| **Live EDGAR vs frozen eval?** | Interactive `ask` can fetch latest filings; **paper repro is offline** on pinned bundle—always distinguish demo snapshot from eval corpus. |
| **Why not use FinanceBench directly?** | Reproducibility and **graph-resolvable bindings**—our items reference accessions and section paths in **our** materialized graphs. |
| **Docling vs custom parser?** | Docling + Arelle for XBRL; we add SEC-specific consolidation, HTML merge, graph mapper—not a from-scratch XBRL parser. |
| **Enterprise deployment?** | Same Docling in **Red Hat AI** pipelines; graph snapshots as artifacts; LM Studio or served models for agent; Gemini or internal judge for audit. |

**If time remains:** Open [interactive AAPL graph](https://caldeirav.github.io/agentic-graphrag-finance/assets/aapl-eval-graph/visualization.html?v=2)—click through FinAgentBench path (two 10-Ks, Item 7, temporal link).

**If challenged on low task_success:** Agree—that is why we separate metrics and publish trajectories. High MRR proves navigation often works; moderate task_success defines the research frontier (synthesis/narrative), not a reason to hide structural evaluation.

**Docs to point people to:** Walkthrough for implementers, custom-judge doc for eval authors, research-reproduction for paper reruns.

**Close:** Thank FINOS stream; repeat GitHub URL; offer to follow up on benchmark design or Docling XBRL edge cases.

---

## Appendix A — Suggested timing (45-minute slot)

| Block | Slides | Minutes |
|-------|--------|---------|
| Problem & prior art | 1–6 | 8 |
| Thesis & architecture | 7–10 | 7 |
| Graph materialization drill-down | 11–14 | 8 |
| Agent drill-down (YoY demo) | 15–21 | 12 |
| Evaluation & benchmark generation | 22–26 | 8 |
| Takeaways & blueprint | 27–29 | 2 (+ Q&A) |

Adjust by cutting Slide 6 (landscape) or compressing Slides 17–19 if live demo runs long.

---

## Appendix B — Live demo script (agent execution)

**Pre-run (before session):**

```bash
uv run agent-query materialize --ticker AAPL
export USE_MOCK_LLM=0 USE_MOCK_JUDGE=0
uv run agent-query ask --ticker AAPL --trace verbose \
  --query "How did total net sales change year over year?"
uv run mlflow ui --backend-store-uri sqlite:///mlflow.db
```

**Narration beats (expanded — ~5–7 min live demo):**

1. **Before `ask`:** Show `data/graphs/AAPL/index.json` or manifest— “This question runs against a **snapshot** with N filings; macro can only bind what was materialized.”

2. **Macro binding panel:** Point at `selected_accessions` (two 10-Ks), `comparison_mode: YoY`, fiscal labels. Say: “No revenue numbers yet—only **scope** decisions validated against the manifest.”

3. **Intent panel:** Highlight `numeric` and `source_bias: xbrl_primary`. Say: “If this were a risk-factor question, intent would flip meso to Item 1A on the same graph.”

4. **Meso / TOC planner:** Show two `xbrl_bucket` section IDs—one per filing. Say: “We did not search the whole filing embedding index—we **opened the XBRL drawer** in each annual report.”

5. **Micro evidence table:** Read both `fact_to_excerpt` strings side by side—FY2024 vs FY2025 revenue, same taxonomy concept, different periods. Mention `content_hash` if audience cares about repro.

6. **Synthesis stdout:** Read answer; trace each number back to a chunk ID in the citation list. Say: “Every dollar traceable to a **`CHUNK_XBRL_FACT`** from Docling parse.”

7. **MLflow artifacts:** Open `agent_trajectory.json`—scroll `document_route` → `graph_traversal` → `evidence`. Then `evaluation/judge_verdict.json`—read one criterion justification aloud (e.g. `routing_decisions: 1.0` because both 10-Ks and XBRL sections match YoY net sales).

8. **FINOS punchline:** “For regulated use, this JSON is as important as the answer string—we can replay **where** the system looked.”

**Fallback:** If network or LM Studio unavailable, use `--trace` capture from a prior run or walk through [end-to-end-walkthrough.md](end-to-end-walkthrough.md) trace excerpts on slides.

---

## Appendix C — Live demo script (benchmark item grounding)

Show one **`finagentbench`** item from the published bundle (conceptually):

- **Question:** Compare net sales discussion across the two most recent 10-K filings.
- **Expected paths:** `0000320193-24-000123/Item7` and `0000320193-24-000076/Item7` (see [eval_context.md](assets/aapl-eval-graph/eval_context.md)).
- Open `corpus/graph_node_index.json` — verify paths exist.
- Explain Gemini authoring + validator rejection if path hallucinated.

Optional CLI inspect:

```bash
jq -r '.question' data/benchmarks/custom-judge/v2.0.0/items/dev.jsonl | head
jq 'select(.inspiration_profile=="finagentbench")' \
  data/benchmarks/custom-judge/v2.0.0/items/dev.jsonl | head -1
```

---

## Appendix D — External reference bibliography (speaker crib sheet)

| Reference | URL |
|-----------|-----|
| FinanceBench (Isenberg et al., 2023) | https://arxiv.org/abs/2311.11944 |
| FinDER (Linq-AI-Research, 2025) | https://arxiv.org/abs/2504.15800 |
| FinAgentBench (2025) | https://arxiv.org/abs/2508.14052 |
| EDGAR-CORPUS (Loukas et al., 2021) | https://arxiv.org/abs/2109.14394 |
| Docling | https://github.com/docling-project/docling |
| Docling XBRL conversion guide | https://docling-project.github.io/docling/examples/xbrl_conversion/ |
| docling-graph | https://github.com/docling-project/docling-graph |
| docling-graph documentation | https://docling-project.github.io/docling-graph/ |
| docling-graph visualization | https://github.com/docling-project/docling-graph/blob/main/docs/fundamentals/graph-management/visualization.md |
| LangGraph | https://github.com/langchain-ai/langgraph |
| SEC EDGAR | https://www.sec.gov/edgar |
| XBRL International | https://www.xbrl.org/ |
| Red Hat AI (Docling in enterprise stacks) | https://www.redhat.com/en/blog/red-hat-ai-modular-building-blocks-scalable-repeatable-model-customization |
| agentic-graphrag-finance repo | https://github.com/caldeirav/agentic-graphrag-finance |
| Interactive AAPL eval graph | https://caldeirav.github.io/agentic-graphrag-finance/assets/aapl-eval-graph/visualization.html?v=2 |

---

## Appendix E — FINOS AI Evaluation and Benchmarking talking points

Use these explicitly when framing Slides 2, 21, 22, and 23 for the FINOS stream:

1. **Frozen corpus + hash verification** — `repro verify-corpus` / `verify-tables` against `releases/paper-v1.0/expected_checksums.json` models reproducible benchmarking.
2. **Trajectory-as-evidence** — agent plans and graph hops are exported artifacts suitable for compliance review, not just final strings.
3. **Native benchmark generation** — demonstrates how to extend public benchmark *methodologies* (FinanceBench, FinDER, FinAgentBench) without copying non-reproducible third-party rows.
4. **Stratified reporting** — HTML vs XBRL vs mixed evidence strata prevent misleading pooled comparisons—relevant when FINOS working groups compare vendor systems fairly.
5. **Open stack** — Docling + docling-graph + LangGraph lowers barrier for community reference implementations alongside commercial offerings.

---

*Speaker notes include suggested timing per slide (~45 min talk + Q&A). Align live numbers with `releases/paper-v1.0/expected_checksums.json` before presenting.*
