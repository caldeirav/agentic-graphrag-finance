# Evaluation paths in this graph

This demo graph is extracted from the custom-judge **2.0.0** bundle
(merged XOM + CAT GraphSnapshots) for three representative `dev.jsonl` items.
The graph shows the **union** of all three evaluation paths plus a XOM `TEMPORAL_TRANSITION`
link between consecutive filings. Select an item to overlay path rings only — nodes stay visible.

## financebench — `v2-financebench-0594`

**Question:** What were the total proceeds, in billions of U.S. dollars, from ExxonMobil's divestment activities, which included the sale of its Singapore retail fuels business and Mobil Argentina S.A., as reported in their 2025 annual filing?

**Expected section paths:**
- `0000034088-26-000067/ITEM 7. MANAGEMENT'S DISCUSSION`

**Demo synthesis path:** `numeric_xbrl_deterministic`

**Demo cited nodes:**
- `doc-0000034088-26-000067-html-business_description-45-body`
- `doc-0000034088-26-000067-html-business_description-46-body`

---

## finder — `v2-finder-0002`

**Question:** According to its 2025 annual report, what specific business sales were part of ExxonMobil's $1.1 billion in divestment activities?

**Expected section paths:**
- `0000034088-26-000067/ITEM 7. MANAGEMENT'S DISCUSSION`

**Demo synthesis path:** `live_llm`

**Demo cited nodes:**
- `doc-0000034088-26-000067-html-business_description-45-body`
- `doc-0000034088-26-000067-html-business_description-46-body`

---

## finagentbench — `v2-finagentbench-0095`

**Question:** Compare how Caterpillar and Exxon Mobil discuss risks related to international trade policies and geopolitical conflicts in their recent filings. In which section of their reports do both companies primarily address these concerns?

**Expected section paths:**
- `0000018230-26-000021/Item 1A. Risk Factors`
- `0000034088-26-000067/ITEM 1A. RISK FACTORS`

**Demo synthesis path:** `comparison_narrative_deterministic`

**Demo cited nodes:**
- `doc-0000018230-26-000021-html-risk_factors-1-body-7`
- `doc-0000034088-26-000067-html-risk_factors-59-body`

---
