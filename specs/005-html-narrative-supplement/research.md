# Research: Supplementary HTML Narrative & Intent Router (005)

**Date**: 2026-05-21 | **Plan**: [plan.md](./plan.md)

## R1 — Narrative HTML artifact source

**Decision**: Prefer **inline/iXBRL HTML** already in the cached XBRL package (`*_htm.xml` or companion HTML extracted from the instance directory after zip unpack). Fall back to downloading the primary filing **`.htm`** from EDGAR `index.json` when inline is missing or fails section-extraction suitability heuristics (empty body, no Item headings).

**Rationale**: Matches spec clarification and constitution II (XBRL package is primary). Reuses `edgar_xbrl` cache layout; avoids extra network when inline suffices.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Always fetch separate `.htm` | Redundant bandwidth; diverges from cached package truth |
| sec-api HTML-only endpoint | Out of scope; violates XBRL-first path |
| Parse narrative from XBRL text blocks only | Misses MD&A prose not modeled as taxonomy facts |

## R2 — HTML section extraction library

**Decision**: v1 uses **`beautifulsoup4`** + `lxml` (html.parser fallback) with **Item-heading regex** map (`Item 1`, `Item 1A`, `Item 7`, `Management's Discussion`, `Risk Factors`). Emit `NarrativeSectionKind` enum on each `SectionBlock`.

**Rationale**: SEC HTML is noisy; regex-on-raw-string is brittle on table-heavy 10-K inline files. BS4 is lightweight and common in document pipelines.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Full Docling HTML pipeline | Heavier; duplicates XBRL docling path; slower materialize |
| stdlib `html.parser` only | Workable for fixtures; higher flake rate on real inline iXBRL |
| LLM section segmentation | Violates grounding/traceability for structure; cost per filing |

## R3 — ParsedDocument merge strategy

**Decision**: Extend `SectionBlock` with `source_type: EvidenceSourceType` default `XBRL`. After XBRL parse, `merge_html_narrative(doc, html_sections)` **appends** HTML sections with new `section_id` prefix `html-`; recompute `content_hash` over canonical merged JSON. **No** overwrite of existing XBRL section IDs.

**Rationale**: Single artifact per accession (FR-003b); graph loader unchanged path (`data/parsed/{ticker}/{accession}.json`).

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Sidecar `*-html.json` | Violates FR-003b; doubles loader logic |
| Replace MD&A-like XBRL sections | Risks numeric conflation; violates FR-002 |

## R4 — Intent router placement and contract

**Decision**: New LangGraph node **`intent_router`** runs **after** `macro_router` (filing set bound) and **before** `meso_router`. Outputs `IntentRouterTrace` on state; `meso_router` may boost HTML section labels when `query_intent=qualitative`.

**Rationale**: Macro handles **which filings**; intent router handles **which source class** (XBRL vs HTML). Keeps `query_intent` canonical per spec edge case.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Fold into `meso_router` only | No structured trace before section rank; harder SC-006 |
| Run after meso | Too late to bias section shortlist toward MD&A HTML |

## R5 — LLM router + keyword fallback

**Decision**: LLM prompt returns JSON `{"query_intent": "numeric|qualitative|hybrid"}`. On empty/invalid JSON, timeout, or `USE_MOCK_LLM=1`, run **`classify_intent_keywords(query)`** with lexicons in `configs/intent_router.yaml` (revenue/EPS → numeric; risk/MD&A/management → qualitative; trend+explain → hybrid).

**Rationale**: Spec FR-006/014; mirrors `macro_router._extract_json_from_llm` pattern; ask must not fail on router alone.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Heuristic-only | Misses hybrid nuance; spec requires LLM router |
| Fail ask on router error | Violates edge case and FR-006 |

## R6 — Observability (router trace)

**Decision**: Add `IntentRouterTrace` Pydantic model; embed on `TrajectoryRecord.intent_router`. `build_trajectory_from_state` copies from `state["intent_trace"]`. MLflow: `log_params` for `query_intent`, `intent_source`, `source_bias_applied`; `log_dict` artifact `intent_router.json` (full trace including optional `router_raw_label`, `router_latency_ms`).

**Rationale**: FR-013–016, SC-006/007; evaluation `trajectory_fidelity_score` can assert field presence without parsing LLM rationale in `macro_plan.rationale`.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Only MLflow params | Insufficient for fallback reason and raw label |
| Store in `macro_plan.rationale` | Unstructured; violates FR-015; overwrites macro semantics |

## R7 — Micro-extractor source bias

**Decision**: Multiply relevance score by bias factor from `source_bias_applied`: `xbrl_primary` → XBRL nodes ×1.5, HTML ×0.7; `html_primary` inverted; `blended` → no multiplier but require min one HTML chunk in top-K when qualitative/hybrid and HTML nodes exist.

**Rationale**: Implements FR-006/007 without new graph edges; uses `GraphNode.properties["source_type"]`.

**Alternatives considered**:

| Alternative | Rejected because |
|-------------|------------------|
| Separate HTML subgraph query | Duplicate traversal; breaks unified snapshot |
| Filter out HTML for numeric | Too rigid for hybrid queries |

## R8 — Qualitative benchmark pilot

**Decision**: Tag ≥10 items in project benchmark (or FinAgentBench subset) with `requires_narrative: true`; pilot issuer **AAPL** 10-K members from 003 corpus. SC-001 measured on that subset post-implementation.

**Rationale**: Spec assumption deferred to planning; unblocks `/speckit-tasks` acceptance tests.
