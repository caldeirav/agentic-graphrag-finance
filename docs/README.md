# Documentation index

Guides for operators and researchers using this repository.

## Start here

| Guide | Audience | Contents |
|-------|----------|----------|
| [README](../README.md) | Everyone | Two workflows: interactive `ask` vs paper `repro` |
| [End-to-end walkthrough](end-to-end-walkthrough.md) | New contributors | XBRL, Docling, graph build, agent stages, judge, MLflow |
| [Research reproduction](research-reproduction.md) | Paper repro | **paper-v2.0** (current), smoke gate, five variants, defer-judge, report, checksums |

## Evaluation and benchmarks

| Guide | Contents |
|-------|----------|
| [Custom-judge dataset generation](custom-judge-dataset-generation.md) | Live EDGAR → graph → Gemini items → publish bundle (v1.x and **v2.0**) |
| [Benchmark reproduction](benchmark-reproduction.md) | Legacy `sec-benchmark` notes; paper repro defers to research-reproduction |

## Operator checklists

| Guide | Contents |
|-------|----------|
| [Navigation trace usability](navigation-trace-usability-checklist.md) | Manual checks for `--trace` output |
| [Macro trace usability](macro-trace-usability-checklist.md) | Macro binding trace review |

## Research

| Doc | Contents |
|-----|----------|
| [Research proposal](research-proposal.md) | Paper abstract and approach (high level) |

## Spec Kit quickstarts (feature folders)

| Feature | Quickstart |
|---------|------------|
| 011 custom-judge | [specs/011-judge-eval-dataset/quickstart.md](../specs/011-judge-eval-dataset/quickstart.md) |
| 012 research repro | [specs/012-research-repro-kit/quickstart.md](../specs/012-research-repro-kit/quickstart.md) |
| 013 eval acceleration | [specs/013-benchmark-eval-acceleration/quickstart.md](../specs/013-benchmark-eval-acceleration/quickstart.md) |
| 014 results viewer | [specs/014-repro-results-viewer/quickstart.md](../specs/014-repro-results-viewer/quickstart.md) |
| 015 eval validity | [specs/015-repro-eval-validity/quickstart.md](../specs/015-repro-eval-validity/quickstart.md) |
| 016 fair outcome | [specs/016-fair-outcome-scoring/quickstart.md](../specs/016-fair-outcome-scoring/quickstart.md) |
| **017 custom-judge v2.0** | [specs/017-custom-judge-v2/quickstart.md](../specs/017-custom-judge-v2/quickstart.md) |

**Current paper release:** `releases/paper-v2.0/` with baseline checksums in `expected_checksums.json`.
