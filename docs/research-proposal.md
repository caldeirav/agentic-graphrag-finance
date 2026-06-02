## **Title**

Graph-Grounded Agentic Retrieval: Enhancing Multi-Stage Reasoning over XBRL Financial Disclosures

## **Abstract**

Large language model (LLM) agents have demonstrated significant potential in complex reasoning tasks, yet they frequently struggle in specialized domains such as finance, where information is dense, highly structured, and distributed across massive regulatory filings. We introduce a novel Graph-based Agentic Retrieval-Augmented Generation (Agentic GraphRAG) framework designed specifically to answer ambiguous, real-world financial queries. Utilizing the open-source docling parser and docling-graph, we transform eXtensible Business Reporting Language (XBRL) documents (e.g., 10-K, 10-Q) into hierarchical, metadata-enriched knowledge graphs. These document graphs capture the inherent structural semantics of financial reporting, bridging narrative text, footnotes, and tabular data.

Furthermore, we present a multi-stage retrieval architecture where an autonomous LLM agent navigates the graph—first reasoning over the appropriate document type and temporal scope, then traversing structural relationships, and finally extracting specific granular chunks. To measure the effectiveness of this approach, we benchmark the agent's decision-making paths and retrieval accuracy against existing baselines. Extensive experiments demonstrate that our XBRL-aware graph retrieval significantly enhances the logical coherence and accuracy of financial question answering.

## **Description of the Research Approach**

### **1\. Data Ingestion & Structured Graph Construction**

The foundation of the research relies on accurately transforming unstructured and semi-structured financial documents into queryable graphs.

* **Parsing with Docling:** We will process raw SEC filings (HTML/XBRL formats) using docling to extract layout-aware text, tables, and figures, ensuring that nested structures (like balance sheets) are not lost to traditional flat-text chunking.  
* **Graph Building with Docling-Graph:** We will map the extracted elements into an entity-relationship graph. The graph will contain document-level nodes (e.g., "Q3 2023 10-Q"), section-level nodes (e.g., "Item 1A: Risk Factors"), and chunk-level nodes (paragraphs, specific XBRL table cells). Edges will denote structural hierarchy, semantic similarity, and temporal sequences (e.g., Q2 to Q3).

### **2\. Multi-Stage Agentic Retrieval**

To handle ambiguous, real-world queries (e.g., *"How do the supply chain risk factors in Apple's latest annual report compare to their previous quarter?"*), we will implement an LLM agent capable of multi-stage reasoning.

* **Stage 1: Document Selection (Macro-Routing):** The agent formulates a plan and queries the graph to filter down to the correct document types (e.g., recognizing that "annual report" maps to a 10-K, while "previous quarter" requires the preceding 10-Q).  
* **Stage 2: Graph Navigation (Meso-Routing):** The agent traverses the structural edges of the graph to locate the specific sections relevant to the query (e.g., navigating to "Management's Discussion and Analysis").  
* **Stage 3: Information Extraction (Micro-Routing):** The agent retrieves the specific chunk or table row necessary to formulate the final answer.

### **3\. Experimental Setup & Benchmarking**

To rigorously measure the effectiveness of our approach, we will evaluate both the final outcome (accuracy) and the agent's intermediate decision-making steps (trajectory). To this extent, we will leverage existing research and associated state-of-the-art financial datasets and benchmarks as well as EDGAR as source to build our own evaluation dataset. Key research and existing datasets considered include:

* [**FinDER (Financial Dataset for Evaluating RAG)**](https://huggingface.co/datasets/Linq-AI-Research/FinDER)**:** Based on the paper [*FinDER: Financial Dataset for Question Answering and Evaluating Retrieval-Augmented Generation*](https://arxiv.org/abs/2504.15800), this dataset will be used to test the system on ambiguous, real-world financial queries where retrieval is the primary bottleneck.  
* [**FinAgentBench**](https://www.kaggle.com/competitions/acm-icaif-25-ai-agentic-retrieval-grand-challenge/data)**:** Drawn from the paper [*FinAgentBench: A Benchmark Dataset for Agentic Retrieval in Financial Question Answering*](https://arxiv.org/abs/2508.14052), this dataset is ideal for testing the LLM agent's ability to perform multi-stage retrieval (e.g., intelligently selecting a 10-Q vs. 10-K before finding the specific chunk).  
* [**FinanceBench**](https://github.com/patronus-ai/financebench)**:** Based on [*FinanceBench: A New Benchmark for Financial Question Answering*](https://arxiv.org/abs/2311.11944), this high-quality, expert-verified benchmark will test if the model can extract specific pieces of information within long 10-K documents and report them accurately.  
* [**EDGAR-CORPUS**](https://huggingface.co/datasets/eloukas/edgar-corpus)**:** Based on [*EDGAR-CORPUS: Billions of Tokens Make The World Go Round*](https://arxiv.org/abs/2109.14394), this massive ingestion framework helps us to understand how to construct our own custom evaluation dataset. Enabling such scale helps us to test how well our docling pipeline scales to extract clean JSON, Markdown, and Graphs from raw SEC HTML/XBRL filings, and allows us to evaluate specific multi-hop edge cases not covered by existing benchmarks.