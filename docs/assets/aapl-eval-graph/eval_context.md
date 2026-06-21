# Evaluation paths in this graph

This demo graph mirrors three accepted custom-judge items used in CI.
Select a scenario in the interactive visualization to overlay **019 investigation**
fields: expected vs visited section paths, cited chunk nodes, synthesis path, and
engineering failure taxonomy (`binding_error`, `comparison_narrative_miss`, etc.).

## financebench — `0.0.0-financebench-001`

**Question:** What was total net sales in the most recent fiscal year?

**Expected section paths:**
- `0000320193-24-000123/Item7`

**Demo synthesis path:** `numeric_xbrl_deterministic`

**Demo cited nodes:**
- `chunk-xbrl-net-sales-fy2024`
- `chunk-item7-p1`

---

## finder — `0.0.0-finder-001`

**Question:** What risk factors does the company highlight for supply chain?

**Expected section paths:**
- `0000320193-24-000123/Item1A`

**Demo synthesis path:** `live_llm`

**Demo cited nodes:**
- `chunk-item1a-p1`

---

## finagentbench — `0.0.0-finagentbench-001`

**Question:** Compare net sales discussion across the two most recent 10-K filings.

**Expected section paths:**
- `0000320193-24-000123/Item7`
- `0000320193-24-000076/Item7`

**Demo synthesis path:** `comparison_narrative_deterministic`

**Demo cited nodes:**
- `chunk-item7-p1`
- `chunk-item7-old-p1`

---

## 019 binding miss demo — `demo-binding-miss-019`

Illustrates `MaterializationAudit.binding_miss` when a comparison question
visits FY2024 Item 7 but never opens FY2023 Item 7. Investigation pack would
suggest `binding_error` and link both EDGAR filings for manual review.
