from datetime import date

from models.enums import EvidenceSourceType
from models.filing import FilingRef
from models.query import EvidenceChunk
from retrieval.synthesis import _synthesize_template


def test_template_citations_include_source_type() -> None:
    filing = FilingRef(
        cik="1",
        accession="1-1",
        form_type="10-K",
        filed_at=date(2024, 1, 1),
        period_end=date(2024, 1, 1),
        source_uri="x",
    )
    evidence = [
        EvidenceChunk(
            chunk_node_id="n1",
            excerpt="Risk factors include supply chain.",
            content_hash="h1",
            citation_label="Risk",
            source_type=EvidenceSourceType.HTML,
        )
    ]
    out = _synthesize_template(evidence, "risk factors?", [filing])
    assert "[HTML]" in out["answer"].text
