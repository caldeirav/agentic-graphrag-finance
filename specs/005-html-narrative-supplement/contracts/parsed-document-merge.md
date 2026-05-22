# Contract: ParsedDocument Merge (XBRL + HTML)

**Feature**: 005-html-narrative-supplement

## Single artifact rule (FR-003b)

| Path | Content |
|------|---------|
| `data/parsed/{ticker}/{accession}.json` | One `ParsedDocument` with XBRL and HTML sections |

Sidecar `*-html.json` files are **not** permitted in v1.

## Merge API (parsing layer)

```python
# src/parsing/html_narrative.py

def extract_narrative_sections(html_path: Path, *, form_type: str) -> list[SectionBlock]: ...

def merge_html_into_document(
    doc: ParsedDocument,
    html_sections: list[SectionBlock],
    *,
    html_artifact_path: str,
    status: HtmlNarrativeStatus,
) -> ParsedDocument: ...
```

## Section ID convention

| source_type | section_id prefix | Example |
|-------------|-------------------|---------|
| `XBRL` | existing (`sec-`, table ids) | unchanged |
| `HTML` | `html-` | `html-item7-mda` |

## Validation (`parsing/validators.py`)

- XBRL sections retain `source_type=XBRL` (default).
- HTML sections MUST have `source_type=HTML` and non-empty `text` or explicit absent marker.
- Duplicate titles across sources allowed; **distinct** `section_id` required (no collapse).

## Graph layer consumption

`docling_graph_mapper` reads `SectionBlock.source_type` → `GraphNode.properties["source_type"]`.

## Forbidden in parsing layer

- LangGraph / LLM calls
- Graph build / snapshot write
- Benchmark evaluation
