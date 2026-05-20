"""Issuer-level multi-filing corpus orchestration (fetch only)."""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

import yaml

from ingestion.edgar_client import list_recent_filings, resolve_identifier, resolve_ticker
from ingestion.settings import is_fixture_ingestion
from models.corpus import (
    CorpusDefinition,
    CorpusDefinitionMode,
    CorpusMaterializationJob,
    CorpusMember,
    CorpusMemberStatus,
    FiscalPeriodLabel,
    infer_fiscal_year_end_month,
)
from models.filing import FilingRef
from models.ingestion import FilingResolution

logger = logging.getLogger(__name__)


class CorpusCapExceededError(ValueError):
    """Corpus definition resolves more filings than max_filings allows."""


def _issuer_cik_ticker(issuer_id: str) -> tuple[str, str]:
    if issuer_id.isalpha() and len(issuer_id) <= 5:
        return resolve_ticker(issuer_id), issuer_id.upper()
    return issuer_id, issuer_id.upper() if issuer_id.isalpha() else "UNKNOWN"


def load_corpus_defaults(config_path: Path | None = None) -> dict:
    path = config_path or Path("configs/corpus.yaml")
    if not path.exists():
        return {"max_filings": 12, "trailing_10k": 1, "trailing_10q": 4}
    return yaml.safe_load(path.read_text()) or {}


def default_corpus_definition(issuer_id: str, *, ticker: str | None = None) -> CorpusDefinition:
    cfg = load_corpus_defaults()
    key = (ticker or issuer_id).upper()
    return CorpusDefinition(
        issuer_id=key,
        mode=CorpusDefinitionMode.DEFAULT_TRAILING,
        max_filings=int(cfg.get("max_filings", 12)),
        trailing_10k=int(cfg.get("trailing_10k", 1)),
        trailing_10q=int(cfg.get("trailing_10q", 4)),
        form_types=list(cfg.get("form_types", ["10-K", "10-Q"])),
    )


def _definition_hash(definition: CorpusDefinition) -> str:
    payload = definition.model_dump(mode="json")
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def resolve_corpus_members(definition: CorpusDefinition) -> list[FilingResolution]:
    """Resolve filing list from corpus definition without downloading."""
    if definition.mode == CorpusDefinitionMode.EXPLICIT_ACCESSIONS:
        if not definition.accessions:
            raise ValueError("explicit_accessions mode requires accessions list")
        cik, ticker = _issuer_cik_ticker(definition.issuer_id)
        resolutions = []
        for acc in definition.accessions:
            if is_fixture_ingestion():
                from ingestion.edgar_client import _fixture_resolution

                resolutions.append(
                    _fixture_resolution(ticker=ticker, cik=cik, accession=acc, form_type="10-Q")
                )
            else:
                resolutions.append(
                    resolve_identifier(ticker=ticker, cik=cik, accession=acc, form_type="10-K")
                )
    elif definition.mode == CorpusDefinitionMode.DATE_RANGE:
        cik, ticker = _issuer_cik_ticker(definition.issuer_id)
        pool = list_recent_filings(cik=cik, ticker=ticker, form_types=definition.form_types)
        resolutions = []
        for res in pool:
            if definition.period_start and res.period_end < definition.period_start:
                continue
            if definition.period_end and res.period_end > definition.period_end:
                continue
            resolutions.append(res)
    else:
        cik, ticker = _issuer_cik_ticker(definition.issuer_id)
        pool = list_recent_filings(cik=cik, ticker=ticker, form_types=definition.form_types)
        tens_k = [r for r in pool if r.form_type == "10-K"][: definition.trailing_10k]
        tens_q = [r for r in pool if r.form_type == "10-Q"][: definition.trailing_10q]
        resolutions = tens_k + tens_q

    if len(resolutions) > definition.max_filings:
        raise CorpusCapExceededError(
            f"Corpus resolves {len(resolutions)} filings but max is {definition.max_filings}. "
            "Narrow scope via accessions or date range."
        )
    return resolutions


def materialize_corpus_members(
    definition: CorpusDefinition,
    *,
    force_refresh: bool = False,
) -> CorpusMaterializationJob:
    """Fetch and cache each corpus member via existing fetch_filing."""
    job_id = str(uuid.uuid4())
    started = datetime.now(UTC)
    resolutions = resolve_corpus_members(definition)
    fy_end = infer_fiscal_year_end_month(
        [
            FilingRef(
                cik=r.cik,
                accession=r.accession,
                form_type=r.form_type,
                filed_at=r.filed_at,
                period_end=r.period_end,
                source_uri=r.edgar_filing_url,
            )
            for r in resolutions
        ]
    )
    members: list[CorpusMember] = []

    for res in resolutions:
        member = CorpusMember(
            resolution=res,
            fiscal_period=FiscalPeriodLabel(
                fiscal_year=res.period_end.year,
                fiscal_quarter=None
                if res.form_type == "10-K"
                else (res.period_end.month - 1) // 3 + 1,
                label="",
            ),
            status=CorpusMemberStatus.PENDING,
        )
        member.fiscal_period = FiscalPeriodLabel.from_filing(
            FilingRef(
                cik=res.cik,
                accession=res.accession,
                form_type=res.form_type,
                filed_at=res.filed_at,
                period_end=res.period_end,
                source_uri=res.edgar_filing_url,
            ),
            fiscal_year_end_month=fy_end,
        )
        try:
            from ingestion import fetch_filing

            fetch_filing(
                resolution=res,
                force_refresh=force_refresh,
            )
            member.status = CorpusMemberStatus.INCLUDED
        except Exception as exc:
            logger.warning("corpus member fetch failed %s: %s", res.accession, exc)
            member.status = CorpusMemberStatus.FAILED
            member.failure_reason = str(exc)
        members.append(member)

    return CorpusMaterializationJob(
        job_id=job_id,
        corpus_definition=definition,
        members=members,
        started_at=started,
        completed_at=datetime.now(UTC),
    )


def corpus_definition_hash(definition: CorpusDefinition) -> str:
    return _definition_hash(definition)
