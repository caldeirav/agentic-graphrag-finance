# Design: LLM-Driven Section Discovery (009 follow-on)

**Status**: Implemented (E + A/C) — 2026-05-23  
**Problem**: Live runs show correct **meso section IDs** after heuristic boosts (`html-md_and_a-2` #1), but **micro** still ranks `html-risk_factors-1-body` above `html-md_and_a-2-body` because chunk scoring rewards the word “risk” globally. Graph **walks** remain shallow (`meso: 2` visits) while costing ~2–5 minutes of LLM time per stage. Section discovery is therefore **not** truly LLM-driven—it is mostly `sections_for_filings()` + `score_section()`, with per-hop LLM calls that barely explore the graph.

**Goal**: Use LLM understanding of **typical 10-K / 10-Q structure** (Items 1, 1A, 7, notes, XBRL facts bucket) to choose where to navigate, with auditable traces and without full-graph scan.

---

## What the latest run shows

| Stage | What worked | What failed |
|-------|-------------|-------------|
| Macro | Bound FY2025 10-K | — |
| Intent | `qualitative` + `html_primary` | — |
| Meso (ranking) | `html-md_and_a-2` ranked #1 (18.8) | LLM walk: 2 visits, 123s; ranking still from enumeration + heuristics |
| Micro | Reached MD&A body chunk (39.0) | **Risk Factors body won (66.0)** → synthesis cited Item 1A |
| Synthesis | Correctly noted MD&A missing | Evidence set was wrong despite right meso section |

**Root cause**: Two independent selection mechanisms—**meso handoff** (heuristic section list) vs **micro evidence ranking** (heuristic chunk scores that still love “risk” + `risk_factors` section_id). LLM hop proposals do not gate either.

---

## Design principles (keep from 009)

1. **LLM proposes; validator approves** (no trusted free-form graph edits).
2. **Structural edges only** for agent hops (`CONTAINS`, `NEXT`, `FOOTNOTE_OF`, `REFERENCES`).
3. **No production heuristic fallback pool** (no flat keyword retrieval)—heuristics may **score LLM candidates**, not replace them.
4. **Trace must explain** section choice and path (console + `navigation_trace.json`).

---

## Option A — Filing “table of contents” planner (recommended primary)

**Idea**: One structured LLM call per bound filing with a **compact TOC** derived from the graph (not raw HTML).

### Inputs (deterministic)

For each `document_root`, emit a JSON list of **section candidates** already in the snapshot:

```json
{
  "accession": "0000320193-25-000079",
  "form_type": "10-K",
  "sections": [
    {
      "section_node_id": "doc-...-html-md_and_a-2",
      "section_id": "html-md_and_a-2",
      "label": "Item 7.",
      "narrative_kind": "md_and_a",
      "item_hint": "7",
      "child_chunk_count": 42
    }
  ]
}
```

- `narrative_kind` / `item_hint`: from materialize-time metadata (extend `SectionBlock` / graph `properties` when HTML narrative is parsed—kinds already exist in `NarrativeSectionKind`).
- Cap TOC size (e.g. top 40 sections by document order); collapse duplicate TOC links.

### LLM task

System prompt encodes **10-K anatomy**:

- Item 1 — Business  
- Item 1A — Risk Factors (standalone risk disclosure)  
- Item 7 — MD&A (operations, liquidity, **risks discussed in management narrative**)  
- Notes / financial statements / XBRL facts bucket — numeric vs narrative  

Return JSON only:

```json
{
  "intent_target": "md_and_a_risk_discussion",
  "ranked_section_node_ids": ["...", "...", "..."],
  "rationale": "...",
  "exclude_kinds": ["risk_factors"]
}
```

Validator: IDs ⊆ TOC, ≤3 per filing, accession in macro scope, optional `exclude_kinds` enforced.

### Graph navigation role

- **Synthetic path** for trace: `doc_root → CONTAINS → section` (from `shortest_structural_path` or stored at materialize).
- Optional **light walk** only inside chosen sections (micro), not for discovery.

### Pros / cons

| Pros | Cons |
|------|------|
| 1–2 LLM calls per filing vs dozens of hop calls | Less “agentic walk” in trace (mitigate with explicit TOC rationale) |
| Directly uses filing structure semantics | Requires TOC metadata quality at materialize |
| Easy to enforce “MD&A not 1A” via `exclude_kinds` | New contract + tests |

**Fit**: Best **cost/latency/accuracy** tradeoff for production; aligns with how analysts actually open a 10-K (TOC → Item).

---

## Option B — Structure-guided graph walk (meso-only discovery)

**Idea**: Replace `sections_for_filings()` enumeration ranking with **walk-only** section discovery from `document_root`, stopping at `SECTION` nodes.

### Mechanics

1. `stop_at_section=True` in meso `_walk_from` (already supported).
2. **Beam width 3–5**: at each hop, LLM ranks neighbors; validator approves top edge; keep multiple paths until budget.
3. **Prompt** includes SEC structure cheat sheet + current path labels + “prefer Item 7 for MD&A risk discussion queries”.
4. **Meso candidates** = SECTION nodes **visited on any beam path**, ranked by LLM path score (not global `score_section`).

### Pros / cons

| Pros | Cons |
|------|------|
| Strongest alignment with 009 “graph-native” story | Slow (your run: 123s for 2 hops—model latency dominates) |
| Rich `meso_paths` in trajectory | LLM may still wander to XBRL bucket without TOC hints |
| No full-section enumeration | Needs batched neighbor scoring (see Option D) |

**Fit**: Good for **eval/gold-path** demos; risky as default production meso without latency work.

---

## Option C — Hybrid: TOC planner + constrained micro walk (recommended rollout)

Combine **A** (meso section pick) + existing micro walk **scoped to chosen sections only**.

### Micro constraints (fixes your failure mode)

1. **Section scope**: Only collect/score chunks whose `section_id` / ancestor section is in meso `ranked_section_node_ids` (drop cross-section leakage from other roots).
2. **Query–kind alignment** (deterministic, post-LLM): If planner sets `intent_target=md_and_a_*`, apply **hard filter or −∞** to chunks under `risk_factors` unless query explicitly asks for Item 1A.
3. **Evidence cap**: Top-k chunks **within** each selected section, then merge (prevents one section dominating via generic keyword boosts).

### Meso trace fields

- `section_discovery_mode`: `toc_planner` | `graph_walk` | `hybrid`  
- `toc_planner_response`: ranked IDs + rationale + excluded kinds  

**Fit**: **Recommended default**—fixes MD&A vs 1A with minimal change to micro walker; keeps one cheap LLM call for meso.

---

## Option D — Batched neighbor scoring (performance enabler)

**Idea**: Keep hop-by-hop validation but **one LLM call per position** that scores **all** outgoing neighbors (≤12), instead of serial proposals.

```json
{
  "ranked_neighbors": [
    {"target_node_id": "...", "edge_type": "CONTAINS", "score": 0.92, "reason": "Item 7 heading"}
  ]
}
```

Validator picks highest valid score; record rejected alts in trace.

**Fit**: Implement alongside **A** or **B** to cut meso/micro time from minutes to seconds per stage.

---

## Option E — Materialize-time section ontology (reduce LLM load)

**Idea**: At graph build, tag every `SECTION` node:

- `narrative_kind`: `business_description` | `risk_factors` | `md_and_a` | `notes` | `financial_statements` | `xbrl_bucket` | `other`  
- `item_number`: `1` | `1A` | `7` | …  
- `is_toc_duplicate`: bool  

Planner (Option A) becomes mostly **deterministic routing** for common patterns:

| Query pattern | Primary kind |
|---------------|----------------|
| MD&A / management discussion | `md_and_a` |
| Item 1A / risk factors (explicit) | `risk_factors` |
| Revenue / EPS / line items | `xbrl_bucket` or statement sections |

LLM only breaks ties or handles `other` sections.

**Fit**: High leverage; data already partially parsed in `html_narrative.py` (`NarrativeSectionKind`).

---

## Option F — Quick win (no new LLM stage): micro section-scoped ranking

**Without waiting for Option A**, fix the observed bug:

1. Pass meso `SectionCandidate` list into micro scoring.  
2. `score_chunk`: if `is_mda_query(query)` and chunk’s `section_id` not in selected meso sections → skip or heavy penalty.  
3. If meso #1 is `md_and_a`, **do not micro-walk** `business_description` / `sec-0` roots (only top meso sections, not “all three ranked” if score gap > threshold).

**Effort**: Small; **does not** make LLM drive discovery but stops Item 1A from beating MD&A when meso already chose MD&A.

---

## Comparison matrix

| Option | LLM drives section pick? | Latency (est.) | Trace quality | Fixes MD&A run? |
|--------|-------------------------|----------------|---------------|-----------------|
| **Current** | Mostly no | Very high | Walk shallow; rank heuristic | Partially (meso only) |
| **A — TOC planner** | Yes | Low | TOC + rationale | Yes (with C) |
| **B — Walk only** | Partially | High | Rich paths | Maybe |
| **C — Hybrid** | Yes | Medium | Best of A + paths | **Yes** |
| **D — Batched hops** | Per-hop | Medium | Rich | Enabler |
| **E — Ontology** | Mostly deterministic | Low | Kind tags | Yes |
| **F — Micro scope** | No | None | Same | **Yes (narrow)** |

---

## Recommended path

### Phase 1 (immediate)

- **F**: Micro evidence restricted to meso-selected section subtrees; MD&A query suppresses `risk_factors` chunks unless meso explicitly includes that section.  
- **D** (optional): Batch neighbor scoring in `propose_next_hop` to cut wall-clock.

### Phase 2 (LLM-driven meso)

- **E**: Add `narrative_kind` / `item_number` on SECTION nodes at materialize.  
- **A + C**: `MesoTocPlanner` LLM call → top 3 `section_node_id`s → micro walk only under those roots.  
- Deprecate production use of global `sections_for_filings()` + `score_section()` **ranking** (keep scoring only to break ties among LLM candidates).  
- Register `navigation_toc_planner` in console trace registry.

### Phase 3 (eval hardening)

- Extend gold-path fixtures with `required_section_kinds` / `forbidden_section_kinds`.  
- Gold-path eval asserts meso picked correct kind before chunk reach.

---

## Prompt sketch (TOC planner — Option A)

```
You route SEC filing questions to the correct Item/section.
10-K structure:
- Item 1: Business
- Item 1A: Risk Factors (standalone statutory risk disclosure)
- Item 7: Management's Discussion and Analysis (MD&A) — operational risks, liquidity, outlook
- Financial statements & notes: accounting policies, line items
- XBRL facts: tagged numbers (not narrative MD&A)

Question: {query}
Filing TOC (section_node_id, label, narrative_kind, item_hint):
{toc_json}

Return JSON:
{
  "ranked_section_node_ids": ["..."],  // max 3
  "primary_narrative_kind": "md_and_a",
  "exclude_section_node_ids": ["..."],
  "rationale": "..."
}
```

For the user’s query, correct behavior: rank `html-md_and_a-*`, **exclude** `html-risk_factors-*` unless the question asks for Item 1A.

---

## Open questions

1. **10-Q**: TOC planner must use 10-Q part headings (Part I Item 2 MD&A, etc.)—extend `item_hint` mapping.  
2. **Multi-filing**: One TOC call per accession (parallel), meso top-3 **per filing** unchanged.  
3. **iXBRL vs legacy `sec-0`**: Prefer HTML narrative sections over empty `sec-0` when `html_primary`.  
4. **CI**: Mock TOC fixtures under `tests/fixtures/navigation_planner/meso/` (extend `mda_risk.json` pattern).

---

## Implementation touchpoints (when approved)

| Component | Change |
|-----------|--------|
| `graph/legacy_builder` / `docling_graph_mapper` | SECTION `properties.narrative_kind`, `item_number` |
| `retrieval/navigation/toc_planner.py` | New LLM TOC planner |
| `retrieval/navigation/walker.py` | `run_meso_navigation` calls planner; remove global enumeration rank |
| `retrieval/navigation/walker.py` | Micro: section-scoped chunk collection |
| `retrieval/orchestration/micro_scoring.py` | Respect meso scope + kind exclusions |
| `tracing/console_trace/registry.py` | `meso_toc_planner` stage |
| `configs/graph_navigation.yaml` | `meso.discovery_mode: toc_planner` |

---

## Success criteria (re-run user query)

```bash
USE_MOCK_LLM=0 uv run agent-query ask --ticker AAPL --trace verbose \
  --query "What are the principal risk factors discussed in management discussion and analysis?"
```

- Meso trace: `primary_narrative_kind=md_and_a`, top sections `html-md_and_a-*` only.  
- Micro top evidence: `html-md_and_a-*-body` chunks, **not** `html-risk_factors-*` unless included by planner.  
- Synthesis: answers from MD&A excerpts; no “evidence is from Item 1A” disclaimer.  
- Wall-clock meso: target **<30s** (TOC + batched hops), not **>120s**.
