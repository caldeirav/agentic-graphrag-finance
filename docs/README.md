# Documentation index

Guides for operators and researchers using this repository.

## Start here

| Guide | Audience | Contents |
|-------|----------|----------|
| [README](../README.md) | Everyone | Two workflows: interactive `ask` vs paper `repro` |
| [End-to-end walkthrough](end-to-end-walkthrough.md) | New contributors | XBRL, Docling, graph build, agent stages, judge, MLflow |
| [Research reproduction](research-reproduction.md) | Paper repro | Phase 1/2, five variants, live vs CI, defer-judge, recovery |

## Evaluation and benchmarks

| Guide | Contents |
|-------|----------|
| [Custom-judge dataset generation](custom-judge-dataset-generation.md) | Live EDGAR → graph → Gemini items → publish bundle |
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
