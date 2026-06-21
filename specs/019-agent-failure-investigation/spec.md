# Feature Specification: Agent Failure Investigation and Remediation

**Feature Branch**: `019-agent-failure-investigation`

**Created**: 2026-06-20

**Status**: Draft

**Input**: Build an agent failure investigation and remediation workflow for the custom-judge evaluation benchmark (v2.0.0 / paper-v1.0 baseline, quality-v2.0.1 draft, paper-v1.1 target). Context: tier-1 review queue (~84 items with MRR≥0.5 or nDCG@10≥0.3 and outcome=0) is mostly agent_failure after GT quality pass (~42/55 annotated agent_failure, ~13 GT patches, selective re-judge improved 1/42). Failures cluster into: (1) macro/route binding errors (wrong company, fiscal year, 10-K vs 10-Q), (2) synthesis template dumps (“Based on N evidence chunks”) despite good retrieval, (3) finagentbench comparison narrative failures, (4) financebench XBRL numeric extraction failures with MRR≈1.0, (5) scale/units mismatches (partially GT, partially agent). Today investigation is split across repro report.html (agent answers), benchmark-dataset review pack (GT/corpus), MLflow traces, and manual SEC URL construction; repro runs suppress console trace (trace_level quiet) and corpus excerpts often degrade to [corpus pointer]. Deliver: (A) Investigation data & UX — unified static failure-investigation pack (HTML+CSV) embedded into the repro report and merging repro results, draft GT, annotations, tier-1 queue metadata, agent answer, citations with excerpts, synthesis path, judge scores and rationale, auto-suggested failure taxonomy (binding_error, retrieval_label_mismatch, synthesis_template_dump, numeric_xbrl_miss, comparison_narrative_miss, abstention, gt_issue_suspected), SEC EDGAR human-readable filing links per bound accession, corpus section excerpts from bundled materialization, and materialization audit (snapshot id, filing refs, expected vs visited section paths, optional subgraph node listing). Extend repro report item drill-down with the same fields and clickable EDGAR links. Optional embed or link materialized graph context for cited chunk nodes (read-only, offline from bundle corpus). (B) Agent execution observability — repro/debug mode that re-runs or replays a supplied item-id cohort with structured trace output (stderr JSONL and/or per-item summary artifact) including macro plan, filing set, meso/micro decisions, synthesis path, and failure flags; stdout progress lines must include item id, variant, synthesis path, citation count, outcome, and weakest judge criterion. (C) Targeted agent remediations — implement and wire fixes for the top failure modes above (prioritize macro binding correctness, numeric XBRL deterministic synthesis coverage, and reducing template-dump fallback when ranked XBRL evidence exists); each fix must ship with focused unit/integration tests and register in a failure-mode regression suite. (D) Pre-repro validation gate — define a frozen tier-1 smoke cohort file derived from review_queue.json; CLI to run agent+judge on cohort across graph-full only, compare before/after metrics (tier-1 zero count, smoke-gate max_mrr_ok_va_zero, synthesis_path distribution), and block full paper-v1.1 repro until cohort acceptance criteria pass. Integrate with existing 018 review CLI (export-queue, export-sheet, annotate, summary) and 014 repro report; do not mutate paper-v1.0 or v2.0.0 locks. Out of scope: changing MRR/nDCG definitions, new judge models, full 200×5 repro as part of this feature, retroactive paper-v1.0 score updates.

## Clarifications

### Session 2026-06-20

- Q: When cohort validation fails, should full paper-v1.1 reproduction be hard-blocked or warn-only? → A: Hard block by default — full paper-v1.1 reproduction exits non-zero unless the cohort gate passed; operators MAY override with an explicit force flag that is recorded in the audit log.
- Q: What should cohort debug do by default — re-run the agent or replay existing checkpoints? → A: Re-run by default — execute agent and judge on the cohort; optional replay-from-checkpoint mode for trace inspection without re-execution.
- Q: How should auto-suggest codes relate to 018 human failure_class values? → A: Dual layer with mapping — auto-suggest uses engineering codes; human annotation keeps 018 classes; system provides a documented default mapping for summaries.
- Q: Should the frozen pre-repro cohort include all tier-1 queue items or a fixed cap? → A: All tier-1 items — the frozen cohort includes every item in the review queue (~84).
- Q: How should graph context be exposed in the failure-investigation pack? → A: Link-first with optional inline — default link to offline bundle graph context; inline embed when pre-rendered data exists.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Unified Failure Investigation View (Priority: P1)

An evaluation operator investigating tier-1 failures (good retrieval, zero outcome) opens a single offline report that shows, for each item, ground truth, agent answer, evidence citations with excerpts, judge scores and rationale, suggested failure category, bound filing links to SEC EDGAR, corpus section text, and materialization audit fields—without switching between separate reproduction and dataset-review artifacts.

**Why this priority**: After the quality-v2.0.1 pass, roughly three quarters of remaining tier-1 zeros are agent failures; split tooling forces manual correlation and slows root-cause identification.

**Independent Test**: Export a failure-investigation pack for 10 tier-1 items from a completed reproduction and draft bundle; verify a reviewer can classify each item’s primary failure mode in under 5 minutes per item using only the pack.

**Acceptance Scenarios**:

1. **Given** completed reproduction output and a draft or published benchmark bundle, **When** the operator generates a failure-investigation pack for a tier-1 queue, **Then** each row merges reproduction scores, ground truth, agent answer, citations with excerpts, judge rationale, human annotations (when present), and materialization audit fields in one static HTML page and companion CSV.
2. **Given** a failure-investigation row, **When** the reviewer opens bound filing links, **Then** each accession resolves to a human-readable SEC EDGAR filing page suitable for spot-checking facts without manual URL construction.
3. **Given** bundled corpus section text exists for an expected section path, **When** the pack renders, **Then** the reviewer sees an excerpt of that section—not only a placeholder pointer.
4. **Given** the reproduction HTML report is generated, **When** the operator expands an item drill-down, **Then** the same investigation fields and EDGAR links appear inline without opening a separate artifact.
5. **Given** cited evidence nodes exist in the bundled corpus, **When** the operator follows the graph-context link, **Then** an offline bundle graph context view opens showing the subgraph around cited nodes; when pre-rendered inline context exists, it MAY also appear embedded in the drill-down.

---

### User Story 2 - Auto-Suggested Failure Taxonomy (Priority: P1)

A reviewer triaging tier-1 items receives a system-suggested failure category derived from reproduction signals (retrieval metrics, answer shape, judge scores, binding audit), which they may accept or override when recording a human annotation.

**Why this priority**: Manual classification alone does not scale across 84 tier-1 items; suggested taxonomy accelerates consistent triage and aggregates fix priorities.

**Independent Test**: Run taxonomy suggestion on 20 items with known failure patterns; verify at least 70% of suggestions match the reviewer’s final primary class on a stratified sample.

**Acceptance Scenarios**:

1. **Given** an item with high retrieval ranking but a template-style agent answer and zero outcome, **When** taxonomy suggestion runs, **Then** the suggested class is `synthesis_template_dump` or the closest matching category in the defined taxonomy.
2. **Given** an item where judge rationale cites wrong filing form or company, **When** taxonomy suggestion runs, **Then** the suggested class is `binding_error`.
3. **Given** an item with perfect retrieval ranking, XBRL-oriented section paths, numeric ground truth, and a non-numeric agent answer, **When** taxonomy suggestion runs, **Then** the suggested class is `numeric_xbrl_miss`.
4. **Given** a human annotation with a different failure class, **When** history is viewed, **Then** both suggested engineering code and confirmed 018 human class are recorded without overwriting prior annotations.
5. **Given** an auto-suggested engineering code, **When** summary reports aggregate failure counts, **Then** a documented default mapping to 018 human classes is applied unless the reviewer overrides the human class.

---

### User Story 3 - Cohort Debug Observability (Priority: P2)

An engineer debugging agent failures re-runs a supplied list of item identifiers with structured execution tracing enabled (default), producing per-item summaries (routing plan, filing set, evidence decisions, synthesis path, outcome, weakest judge criterion) suitable for comparing before and after remediation. An optional replay mode assembles the same summaries from existing reproduction checkpoints without re-executing the agent.

**Why this priority**: Full reproduction runs suppress detailed trace output; targeted debug runs are required to validate fixes without an eight-hour full reproduction.

**Independent Test**: Re-run a 5-item debug cohort with tracing enabled; verify each item produces a structured summary artifact and stdout progress line containing item id, variant, synthesis path, citation count, outcome, and weakest judge criterion.

**Acceptance Scenarios**:

1. **Given** a cohort file listing item identifiers, **When** the operator runs cohort debug mode on the baseline graph variant (default), **Then** the system re-executes agent and judge for each item and emits a structured trace summary including macro routing, filing set, meso/micro decisions, synthesis path, and failure flags.
2. **Given** cohort debug mode, **When** execution progresses, **Then** stdout progress lines include item id, variant, synthesis path, citation count, outcome score, and weakest judge criterion for every completed item.
3. **Given** a completed debug cohort, **When** the operator compares two runs (before and after a fix), **Then** they can diff synthesis path distribution and tier-1 zero count on the same cohort without re-running the full 200-item benchmark.
4. **Given** existing reproduction checkpoints for cohort items, **When** the operator enables replay mode, **Then** structured trace summaries are assembled from stored trajectories without re-executing the agent.

---

### User Story 4 - Targeted Agent Remediation with Regression Tests (Priority: P2)

A retrieval engineer implements fixes for the highest-frequency agent failure modes—macro binding correctness, numeric fact synthesis when ranked evidence supports it, and reduced template-dump answers—and validates each fix through focused regression tests before requesting a full paper reproduction.

**Why this priority**: Investigation without remediation leaves headline outcome metrics unchanged; fixes must be provably tied to observed failure clusters.

**Independent Test**: For each shipped remediation, run the failure-mode regression suite; verify failing fixtures from tier-1 patterns pass while unaffected baseline cases remain unchanged.

**Acceptance Scenarios**:

1. **Given** a tier-1 item where the question specifies a quarterly filing but the agent bound annual filings, **When** macro binding remediation is applied, **Then** the agent selects the correct form type and fiscal period on a regression fixture derived from that pattern.
2. **Given** ranked XBRL numeric evidence and a numeric question, **When** synthesis remediation is applied, **Then** the agent produces a grounded numeric answer instead of a generic evidence-list template on regression fixtures.
3. **Given** a comparison question requiring cross-filing contrast, **When** comparison synthesis remediation is applied, **Then** the agent answer names both filings and states a substantive contrast on regression fixtures.
4. **Given** any new remediation, **When** the failure-mode regression suite runs in continuous integration, **Then** each fix is registered with at least one automated test that fails without the fix and passes with it.

---

### User Story 5 - Pre-Repro Validation Gate (Priority: P1)

A reproduction operator validates agent improvements on a frozen tier-1 smoke cohort (derived from the review queue) and blocks initiation of full paper-v1.1 reproduction until cohort acceptance criteria are met.

**Why this priority**: Full 200-item × five-variant reproduction is too expensive to use as the first feedback loop; a cohort gate prevents regressions and confirms improvement direction before committing to paper-v1.1.

**Independent Test**: Run the cohort gate before and after a known synthesis fix; verify tier-1 zero count and high-retrieval-zero-outcome cap improve on the cohort while the gate blocks full repro when criteria fail.

**Acceptance Scenarios**:

1. **Given** a completed tier-1 review queue export, **When** the operator materializes a frozen cohort file, **Then** the file lists all tier-1 item identifiers from the queue (approximately 84 items), priority metadata, and provenance (source queue version and export timestamp).
2. **Given** a frozen cohort and baseline graph variant, **When** the operator runs the cohort validation command, **Then** the report includes tier-1 zero count, count of items with strong retrieval but zero outcome, and distribution of auto-suggested failure classes.
3. **Given** cohort metrics after a remediation pass, **When** acceptance criteria are not met, **Then** initiation of full paper-v1.1 reproduction is blocked with a non-zero exit status, failed thresholds are documented, and the operator MAY proceed only via an explicit force override recorded in the audit log.
4. **Given** cohort metrics meet acceptance criteria, **When** the operator proceeds to full reproduction, **Then** the cohort report and baseline comparison are retained as audit artifacts for paper-v1.1.

---

### User Story 6 - Integration with Dataset Quality Review (Priority: P3)

A dataset operator continues using the existing review queue, annotation sheet, and quality summary workflows while failure-investigation artifacts reference the same item identifiers, annotations, and selective re-judge paths.

**Why this priority**: Feature 018 established GT quality workflows; agent investigation must extend—not replace—those tools.

**Independent Test**: Export tier-1 queue via existing review CLI, generate failure-investigation pack for the same items, apply one human annotation, and verify quality summary reflects both GT and agent failure counts.

**Acceptance Scenarios**:

1. **Given** an exported tier-1 review queue, **When** failure-investigation pack generation runs, **Then** it accepts the same queue file and reproduction input paths as the 018 review export commands.
2. **Given** an item annotated as `agent_failure`, **When** failure-investigation summary aggregates results, **Then** that item is excluded from dataset-caused zero-score tallies in the quality pass summary.
3. **Given** selective re-judge after GT patches, **When** failure-investigation pack is regenerated, **Then** updated outcome scores appear without requiring a full agent re-run for GT-only fixes.

---

### Edge Cases

- What happens when reproduction results exist only for a subset of queue items? The pack MUST render available reproduction fields and mark missing items explicitly; taxonomy suggestion MUST degrade gracefully with partial signals.
- What happens when corpus section text is absent for a bound path? The pack MUST show the section path, materialization audit, and EDGAR link; it MUST NOT fail export for the entire cohort.
- What happens when suggested taxonomy conflicts with an existing human annotation? Both values MUST be visible; the human annotation remains authoritative for quality-summary metrics.
- What happens when debug cohort re-run fails mid-batch? Completed items MUST retain partial summaries; the operator MUST be able to resume or retry failed identifiers only.
- What happens when a remediation fix improves cohort metrics but regresses a non-tier-1 item? The failure-mode regression suite MUST include guardrail cases from non-tier-1 items before cohort gate passes.
- What happens when EDGAR link construction lacks CIK metadata? The pack MUST still show accession and form metadata; links MAY be omitted with a documented reason rather than constructing broken URLs.
- What happens when optional graph context for cited chunks is unavailable offline? Drill-down MUST fall back to citation excerpts and section paths without blocking core investigation fields; graph-context links MUST be omitted with a documented reason rather than broken links.
- What happens when cohort gate fails but the operator must run full repro urgently? Full paper-v1.1 reproduction MUST remain blocked by default; an explicit force override MUST be available and MUST append an audit record noting failed thresholds and override rationale.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST generate a unified failure-investigation pack (static HTML plus companion CSV with identical rows) merging reproduction results, benchmark ground truth, tier-1 queue metadata, human annotations when present, agent answers, citation excerpts, judge scores and rationale, synthesis path, auto-suggested failure taxonomy, SEC EDGAR filing links per bound accession, corpus section excerpts when available, and materialization audit fields (snapshot identifier, filing references, expected versus visited section paths, optional cited-node listing).
- **FR-002**: System MUST embed the same investigation fields into reproduction report item drill-down, including clickable EDGAR links where metadata allows.
- **FR-003**: System MUST support read-only offline graph context for cited evidence nodes sourced from the bundled corpus without requiring live network access during review; the default presentation MUST link to an offline bundle graph context panel (subgraph around cited nodes); inline embedding MUST be used when pre-rendered context data exists in the bundle.
- **FR-004**: System MUST auto-suggest a primary failure class for each investigated item from the engineering taxonomy: `binding_error`, `retrieval_label_mismatch`, `synthesis_template_dump`, `numeric_xbrl_miss`, `comparison_narrative_miss`, `abstention`, `gt_issue_suspected`; suggestions MUST remain separate from 018 human annotation classes (`agent_failure`, `gt_too_strict`, etc.); the system MUST provide a documented default mapping from engineering codes to human classes for summary rollups; human annotations MUST remain overridable without loss of history.
- **FR-005**: System MUST support cohort debug mode that, by default, re-executes agent and judge for a user-supplied list of item identifiers on the baseline graph variant with structured trace output (machine-readable event stream and/or per-item summary artifact) covering macro plan, filing set, meso/micro decisions, synthesis path, and failure flags; an optional replay mode MUST assemble the same summaries from existing reproduction checkpoints without re-executing the agent.
- **FR-006**: System MUST emit stdout progress lines during cohort debug and cohort validation runs that include, at minimum: item identifier, variant, synthesis path, citation count, outcome score, and weakest judge criterion.
- **FR-007**: System MUST implement targeted agent remediations prioritized for macro binding correctness, numeric fact synthesis when ranked evidence supports it, and elimination of template-dump answers when ranked structured numeric evidence exists; each remediation MUST register in a failure-mode regression suite.
- **FR-008**: System MUST define a frozen tier-1 smoke cohort file derived from review queue exports that includes **all** tier-1 queue items (not a capped subset), with provenance metadata, and support cohort-only agent-plus-judge execution on the baseline graph variant.
- **FR-009**: System MUST produce a cohort validation report comparing before and after metrics: tier-1 zero count, count of strong-retrieval zero-outcome items, and distribution of suggested failure classes; it MUST hard-block initiation of full paper-v1.1 reproduction when acceptance criteria fail (non-zero exit), unless the operator passes an explicit force override that is recorded in the audit log.
- **FR-010**: System MUST integrate with existing dataset review commands (export-queue, export-sheet, annotate, summary) and existing reproduction report generation without replacing published bundle artifacts as the evaluation lock source of truth.
- **FR-011**: System MUST keep v2.0.0 and paper-v1.0 immutable; agent remediation validation targets paper-v1.1 readiness using draft bundles and new reproduction outputs without retroactive changes to frozen baselines.
- **FR-012**: System MUST retain audit artifacts for cohort validation runs (input cohort hash, metric snapshot, timestamp, operator-configured acceptance thresholds) suitable for paper reproduction sign-off.

### Key Entities

- **Failure Investigation Row**: One benchmark item’s merged investigation record linking reproduction scores, ground truth, agent output, citations, judge verdict, suggested and confirmed failure classes, EDGAR links, corpus excerpts, and materialization audit.
- **Suggested Failure Class**: System-derived primary failure category from the engineering taxonomy; advisory until confirmed or overridden; maps to 018 human classes via a documented default mapping for summaries.
- **Materialization Audit**: Per-item summary of which corpus snapshot and filing bindings were expected versus which sections and evidence nodes the agent actually used.
- **Cohort Debug Summary**: Structured per-item execution record from a traced re-run including routing, evidence, synthesis path, outcome, and judge weakest criterion.
- **Tier-1 Smoke Cohort**: Frozen list of **all** tier-1 item identifiers from the review queue (~84 items) with provenance, used as the pre-repro validation sample.
- **Cohort Validation Report**: Before/after metric snapshot and pass/fail status against acceptance thresholds for tier-1 zeros and high-retrieval-zero-outcome counts.
- **Failure-Mode Regression Case**: Automated test fixture representing a known tier-1 failure pattern; must fail before remediation and pass after.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A trained reviewer completes primary failure classification for tier-1 items using only the unified investigation pack at a median rate of at least one item per 5 minutes on a 10-item sample.
- **SC-002**: Auto-suggested failure taxonomy matches the reviewer’s confirmed primary class on at least 70% of a stratified 20-item audit sample.
- **SC-003**: After prioritized agent remediations pass the failure-mode regression suite and cohort gate, the frozen tier-1 cohort shows at least a 25% reduction in strong-retrieval zero-outcome items compared to the paper-v1.0 baseline cohort snapshot.
- **SC-004**: At least 90% of failure-investigation rows for items with resolvable accession metadata include working EDGAR filing links or an explicit documented omission reason.
- **SC-005**: Cohort validation on the full frozen tier-1 sample (~84 items) completes in under 2 hours on operator hardware documented in the quality-pass runbook, enabling at least one fix-and-retest cycle per working session before full paper-v1.1 reproduction.
- **SC-006**: Operators can diagnose macro binding, template-dump synthesis, and numeric miss failures using cohort debug summaries without opening a separate observability product for at least 80% of tier-1 items in a validation sample.

## Assumptions

- Tier-1 review queue exports (~84 items with strong retrieval and zero outcome) are the **complete** frozen cohort for pre-repro validation; tier-2 and tier-3 items are out of scope unless explicitly added to a separate cohort file.
- The quality-v2.0.1 draft and paper-v1.1 target remain the evaluation context; v2.0.0 and paper-v1.0 locks stay immutable.
- Existing human failure classes from feature 018 (`agent_failure`, `gt_too_strict`, etc.) remain the authoritative annotation taxonomy; auto-suggested engineering codes are a separate layer with a documented default mapping to human classes for summary rollups (e.g. most engineering codes map to `agent_failure`; `gt_issue_suspected` maps to `gt_wrong` or `gt_too_strict` pending reviewer confirmation).
- Bundled benchmark corpus and reproduction checkpoints from paper-v1.0 or successor runs are available locally; missing corpus text falls back to pointers and EDGAR links rather than blocking investigation; graph context uses link-first presentation with inline embed only when pre-rendered bundle data exists.
- Acceptance thresholds for the cohort gate are configured in the paper-v1.1 release manifest or companion quality checklist rather than hard-coded in application logic.
- SEC EDGAR public filing URLs are sufficient for human spot-check; authenticated or paywalled sources are out of scope.
- Full 200-item × five-variant reproduction is explicitly deferred until cohort gate passes; this feature delivers investigation tooling, targeted fixes, and pre-repro validation only.
- Ranking metric definitions (MRR, nDCG@10) and judge model/version remain unchanged; outcome score continues to reflect value alignment on answer ground truth.
