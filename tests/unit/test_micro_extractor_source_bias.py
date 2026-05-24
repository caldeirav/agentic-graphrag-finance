from models.enums import EvidenceSourceType, SourceBias
from retrieval.orchestration.micro_scoring import source_bias_multiplier as _source_bias_multiplier


def test_xbrl_primary_bias() -> None:
    assert _source_bias_multiplier(EvidenceSourceType.XBRL, SourceBias.XBRL_PRIMARY) == 1.5
    assert _source_bias_multiplier(EvidenceSourceType.HTML, SourceBias.XBRL_PRIMARY) == 0.7


def test_html_primary_bias() -> None:
    assert _source_bias_multiplier(EvidenceSourceType.HTML, SourceBias.HTML_PRIMARY) == 1.5
