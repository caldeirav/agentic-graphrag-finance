# Stop Chunking Tables: How We Built an Agentic GraphRAG for Financial Disclosures with Docling

Lately, I have been focused on a practical problem: answering questions over SEC filings without the usual flat-chunking failures.

If you have ever built a retrieval-augmented generation (RAG) pipeline over **10-K** or **10-Q** disclosures, you know the pattern. You chunk text, embed vectors, retrieve top-k passages, and the language model still confuses fiscal periods, misroutes balance-sheet facts, or cites narrative that does not support the number in the answer.

Work like [FinanceBench](https://arxiv.org/abs/2311.11944) shows that generic RAG over long financial documents fails on a large share of expert-style questions—not because the models are useless, but because **filings are structured artifacts**, not flat prose. They combine XBRL-tagged facts, HTML narrative, footnotes, and regulatory section hierarchy. Standard chunking turns tables into word soup and severs numbers from the sections that give them meaning.

Our response is [**agentic-graphrag-finance**](https://github.com/caldeirav/agentic-graphrag-finance): an open-source stack that parses EDGAR packages with **Docling**, maps them into **docling-graph–aligned** knowledge graphs, and runs a **multi-stage LangGraph agent** to bind filings, walk sections, rank evidence, and synthesize **cited** answers. An external judge scores both the answer and the navigation trace. We are still iterating on synthesis quality—but the architecture makes structural mistakes easier to see and measure than in a single-shot retriever.

## The structural shape of financial data

When an analyst reads a 10-K, they navigate:

1. **Which filing(s)?** Annual vs quarterly; this year vs last year for a comparison.
2. **Which section?** MD&A, risk factors, segment footnotes—not random similar paragraphs.
3. **Which evidence?** A table row, an XBRL fact, a footnote tied to a cell.

Flat vector search collapses those decisions into one embedding similarity step. Ask for inventory at fiscal year-end and you may retrieve income-statement prose or the wrong period because the embedding looked close enough.

We preserve three layers of semantics in the graph:

1. **Document-level relationships** — filing type, accession, reporting period, and temporal links between quarterly and annual reports where materialized together.
2. **Layout-level relationships** — sections, paragraphs, and footnotes connected by containment and reference edges.
3. **Tabular and numeric layout** — table rows and XBRL facts kept as first-class chunk nodes with concept, period, and currency metadata—not shredded across arbitrary token windows.

## Docling, XBRL, and a deterministic graph bridge

SEC submissions arrive as **XBRL packages**: instance documents, taxonomy linkbases, and (often) HTML narrative exhibits—not as PDFs waiting for vision models.

**Docling** is open source (from the [Docling project](https://github.com/docling-project/docling), with roots in IBM Research). It is also available as part of **[Red Hat AI](https://www.redhat.com/en/blog/red-hat-ai-modular-building-blocks-scalable-repeatable-model-customization)**—Red Hat’s supported document-intelligence component for preparing enterprise data for RAG, extraction, and model customization, including integration with **Red Hat OpenShift AI** and Kubeflow Pipelines for scaled ingestion. We use the upstream library directly in this project; teams operating on OpenShift can run the same parsing stack as a managed, pipeline-native workload.

We configure Docling with its XBRL backend (Arelle under the hood) to parse instance files against US-GAAP taxonomies and emit a structured **DoclingDocument**. From that we build a normalized **ParsedDocument** that keeps:

- **Metadata** — entity, accession, form type, reporting periods.
- **Narrative blocks** — MD&A prose, risk factors, footnotes (from HTML where present).
- **Numeric facts** — revenue, assets, and other tagged concepts as period-scoped key-value facts.

**Important design choice:** upstream **docling-graph** tutorials often build graphs from PDFs via LLM/VLM extraction pipelines. SEC XBRL is already tagged. We treat docling-graph as a **schema contract**—typed nodes and edges with explicit meaning—and implement a **deterministic mapper** (`Docling → ParsedDocument → GraphSnapshot`) instead of re-extracting structure from prose on every filing.

Typical node types:

- **DOCUMENT** — one filing (e.g. Apple Q3 2024 10-Q).
- **SECTION** — Item 1A, Item 7 MD&A, and similar.
- **CHUNK_*** — paragraphs, table rows, and **CHUNK_XBRL_FACT** nodes for tagged numbers.

Typical edge types:

- **CONTAINS** — document → section → chunk hierarchy.
- **NEXT** — reading order within a section.
- **FOOTNOTE_OF** — footnote linked to a table or fact.
- **REFERENCES** — cross-links where modeled.
- **TEMPORAL_TRANSITION** — optional links between filings on a timeline.

Snapshots are exported as **GraphML** plus a manifest (not a generic opaque database), so traversals are auditable and versioned per issuer.

Minimal Docling XBRL setup (the same pattern our pipeline uses):

```python
from pathlib import Path
from docling.datamodel.backend_options import XBRLBackendOptions
from docling.datamodel.base_models import InputFormat
from docling.document_converter import DocumentConverter, XBRLFormatOption

accession_dir = Path("sec_downloads/AAPL/0000320193-24-000123")  # instance + linkbases together
converter = DocumentConverter(
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
result = converter.convert(accession_dir / "000032019324000123_htm.xml")
docling_doc = result.document  # → ParsedDocument → docling-graph-aligned GraphSnapshot
```

For a full materialize → ask walkthrough with traces and judge output, see the [end-to-end guide on GitHub](https://github.com/caldeirav/agentic-graphrag-finance/blob/main/docs/end-to-end-walkthrough.md).

## Multi-stage agentic retrieval (not one vector search)

Navigation is a **LangGraph** workflow with five stages—not a single retrieval call:

| Stage | What it decides |
|-------|-----------------|
| **Macro routing** | Which accession(s) and temporal anchor match the question (10-K vs 10-Q, latest annual vs prior quarter, comparison pairs). |
| **Intent routing** | Numeric vs qualitative emphasis; comparison vs point lookup. |
| **Meso routing** | Which sections to open—TOC planning, section scoring, graph walking toward MD&A, risk, or footnotes. |
| **Micro extraction** | Which chunks and XBRL facts to rank inside those sections. |
| **Synthesis** | Grounded answer with **ordered citations**; guards against ungrounded numerics and weak comparison evidence. |

Macro, meso, and micro mirror how analysts work; intent and synthesis connect routing to answer quality.

Each stage emits **trace payloads** (binding proposals, visited sections, ranked chunks). A **Gemini-class trajectory judge** scores value alignment and navigation fidelity separately from ranking metrics like **MRR** and **nDCG@10** over cited chunks vs graph-grounded relevance labels.

That split matters in practice: on our frozen ~200-item development benchmark, the full graph agent can show **strong citation ranking** while **task success** (answer alignment) remains moderate—pointing to synthesis and grounding as the active research frontier, not retrieval alone.

## How we evaluate (and what we compare against)

We do not paste rows from public benchmarks. We generate a **native graph-grounded set**—questions and answers bound to real accessions and resolvable section paths—while borrowing **question style** from [FinanceBench](https://arxiv.org/abs/2311.11944), [FinDER](https://arxiv.org/abs/2504.15800), and [FinAgentBench](https://arxiv.org/abs/2508.14052).

Experiments run **offline** on a frozen corpus so every variant sees identical filings. Besides the full **graph-full** agent, we compare to:

- **Flat-chunk** — MiniLM dense retrieval over the same chunks (no graph walk).
- **Ablations** — no macro router (pre-bound filings), no walker (no meso/micro hops), XBRL-only (no HTML narrative).

Stratifying by evidence type (HTML vs XBRL vs mixed) avoids misleading pooled scores when an ablation structurally cannot reach narrative chunks.

## Takeaways for developers building on Docling

1. **Do not treat regulatory filings as flat text.** If your source format is already structured (XBRL, HTML sections, tables), invest in a typed graph before scaling embeddings. Path-finding beats guessing similar paragraphs.
2. **Use docling-graph as a contract, not always as a black-box CLI.** For tagged SEC data, deterministic mapping from Docling output is faster, cheaper, and easier to audit than LLM graph extraction on every document.
3. **Stage your agent and log trajectories.** When answers fail, you need to know whether macro binding, section routing, chunk ranking, or synthesis broke—not one blended retrieval score.
4. **Measure retrieval and outcome separately.** Ranking metrics on citations and judge scores on answers tell different stories; both are necessary for financial QA.
5. **Keep an open stack—and know the enterprise path.** Docling, docling-graph, LangGraph, and local LLM serving (e.g. LM Studio) let you run the full pipeline on your own infrastructure. When you need supported builds and scaled document pipelines, the same Docling tooling is part of Red Hat AI on OpenShift AI—not a separate proprietary parser.

We are still hardening synthesis and multi-filing comparison answers—but graph-grounded agentic retrieval already makes **where the system looked** as inspectable as **what it said**. For financial disclosures, that transparency is not optional.
