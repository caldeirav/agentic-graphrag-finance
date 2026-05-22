# Contract: `agent-query ask` Trace Flags

**Feature**: 007 | **Command**: `uv run agent-query ask`

## Flags

| Flag | Values | Default resolution |
|------|--------|-------------------|
| `--trace` | `quiet`, `normal`, `verbose` | See precedence below |
| `--trace-json` | boolean | `false` |

## Precedence

1. `--trace <level>` if provided
2. else `AGENT_QUERY_TRACE` env (`quiet` \| `normal` \| `verbose`)
3. else `normal` if `sys.stderr.isatty()` else `quiet`

## Output channels

| Stream | Content |
|--------|---------|
| **stdout** | Answer text OR `--json` payload only |
| **stderr** | Human trace sections (if not `quiet`); JSONL trace lines (if `--trace-json`) |

## Level behavior

| Level | stderr human | stderr JSONL | stdout |
|-------|--------------|--------------|--------|
| `quiet` | status footer only (existing) | if `--trace-json` | answer/json |
| `normal` | streaming stage panels + footer | if `--trace-json` | answer/json |
| `verbose` | normal + full prompt/response previews | if `--trace-json` | answer/json |

## Non-goals

- Trace MUST NOT add keys to stdout JSON when only `--json` is set.
- `--trace` MUST NOT change graph routing or evidence selection.
