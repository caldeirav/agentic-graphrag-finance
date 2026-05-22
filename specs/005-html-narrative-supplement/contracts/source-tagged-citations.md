# Contract: Source-Tagged Citations

**Feature**: 005-html-narrative-supplement | **Spec**: FR-008, SC-003

## Evidence chunk (retrieval output)

```python
class EvidenceChunk(BaseModel):
    chunk_node_id: str
    excerpt: str
    content_hash: str
    citation_label: str = ""
    source_type: EvidenceSourceType  # NEW required
    accession: str = ""
    section_id: str = ""
```

Populated from `GraphNode.properties["source_type"]` and filing ref at extraction time.

## Answer / CLI output (FR-008)

JSON and CLI citation rendering MUST include for each citation:

| Field | Example |
|-------|---------|
| `source_type` | `XBRL` or `HTML` |
| `accession` | `0000320193-24-000123` |
| `section_id` / label | `html-item7-mda` or fact concept |

## Trajectory evidence list

`TrajectoryRecord.evidence[]` uses the same `EvidenceChunk` shape; eval judges read `source_type` without re-parsing answer text.

## Ranking invariants (FR-006/007)

| query_intent | Primary citations expected |
|--------------|----------------------------|
| `numeric` | Majority `XBRL` for numeric claims |
| `qualitative` | ≥1 `HTML` when narrative required and available |
| `hybrid` | Both types present when graph has both |

## Forbidden

- Citations without `source_type` on successful ask (SC-003)
- Labeling HTML excerpt as `XBRL` numeric grounding
- Silent omission of `source_type` in `trajectory.json`
