# Documentation index

Guides for operators and researchers using this repository.

## Start here

| Guide | Audience | Contents |
|-------|----------|----------|
| [README](../README.md) | Everyone | Interactive `ask` vs **paper-v1.0** reproduction |
| [End-to-end walkthrough](end-to-end-walkthrough.md) | New contributors | XBRL, Docling, graph build, agent stages, judge, MLflow |
| [Research reproduction](research-reproduction.md) | Paper repro | **paper-v1.0**: five variants × 200 items, verify-tables, report |
| [Custom-judge dataset generation](custom-judge-dataset-generation.md) | Dataset authors | v2.0.0 bundle structure and publish workflow |

## Operator checklists

| Guide | Contents |
|-------|----------|
| [Navigation trace usability](navigation-trace-usability-checklist.md) | Manual checks for `--trace` output |
| [Macro trace usability](macro-trace-usability-checklist.md) | Macro binding trace review |

## Research

| Doc | Contents |
|-----|----------|
| [Research proposal](research-proposal.md) | Paper abstract and approach (high level) |

## Spec Kit (implementation detail)

Feature specs under `specs/{NNN-feature-name}/`. For day-to-day reproduction, use [research-reproduction.md](research-reproduction.md) rather than spec quickstarts.

**Release artifacts:** `releases/paper-v1.0/manifest.yaml` · `releases/paper-v1.0/expected_checksums.json` · bundle `data/benchmarks/custom-judge/v2.0.0/`
