"""Governance budget tracking and fail-stop for dataset generation (012)."""

from __future__ import annotations

from time import monotonic

from models.benchmark_generation import BudgetSnapshot, GovernanceCaps


class GovernanceBudgetExceeded(Exception):
    """Raised when a generation run exceeds configured governance caps."""

    def __init__(self, cap: str, limit: int | float, observed: int | float) -> None:
        self.cap = cap
        self.limit = limit
        self.observed = observed
        super().__init__(f"Governance cap '{cap}' exceeded: {observed} > {limit}")


class BudgetTracker:
    """Tracks counters against ``GovernanceCaps`` with fail-stop semantics."""

    def __init__(self, caps: GovernanceCaps) -> None:
        self.caps = caps
        self._started_at = monotonic()
        self.issuers = 0
        self.filings = 0
        self.items = 0
        self.judge_api_calls = 0
        self.storage_bytes = 0

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            issuers_selected=self.issuers,
            filings_selected=self.filings,
            judge_api_calls=self.judge_api_calls,
            storage_bytes=self.storage_bytes,
            items_accepted=self.items,
        )

    def check_wall_clock(self) -> None:
        elapsed = monotonic() - self._started_at
        if elapsed > self.caps.max_wall_clock_seconds:
            raise GovernanceBudgetExceeded(
                "max_wall_clock_seconds", self.caps.max_wall_clock_seconds, elapsed
            )

    def record_issuer(self, count: int = 1) -> None:
        self.check_wall_clock()
        self.issuers += count
        if self.issuers > self.caps.max_issuers:
            raise GovernanceBudgetExceeded("max_issuers", self.caps.max_issuers, self.issuers)

    def record_filing(self, count: int = 1) -> None:
        self.check_wall_clock()
        self.filings += count
        per_issuer_cap = self.caps.max_filings_per_issuer
        if count > per_issuer_cap:
            raise GovernanceBudgetExceeded("max_filings_per_issuer", per_issuer_cap, count)

    def record_item(self, count: int = 1) -> None:
        self.check_wall_clock()
        self.items += count
        if self.items > self.caps.max_items:
            raise GovernanceBudgetExceeded("max_items", self.caps.max_items, self.items)

    def record_judge_call(self, count: int = 1) -> None:
        self.check_wall_clock()
        self.judge_api_calls += count
        if self.judge_api_calls > self.caps.max_judge_api_calls:
            raise GovernanceBudgetExceeded(
                "max_judge_api_calls", self.caps.max_judge_api_calls, self.judge_api_calls
            )

    def record_storage(self, byte_count: int) -> None:
        self.check_wall_clock()
        self.storage_bytes += byte_count
        if self.storage_bytes > self.caps.max_storage_bytes:
            raise GovernanceBudgetExceeded(
                "max_storage_bytes", self.caps.max_storage_bytes, self.storage_bytes
            )

    def preflight_issuers(self, planned: int) -> None:
        if planned > self.caps.max_issuers:
            raise GovernanceBudgetExceeded("max_issuers", self.caps.max_issuers, planned)

    def preflight_items(self, planned: int) -> None:
        if planned > self.caps.max_items:
            raise GovernanceBudgetExceeded("max_items", self.caps.max_items, planned)
