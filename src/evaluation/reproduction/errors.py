"""Typed errors for reproduction acceleration (013)."""

from __future__ import annotations


class ReproAccelerationError(Exception):
    """Base error for repro acceleration paths."""


class MissingBindingsError(ReproAccelerationError):
    """Benchmark item has no expected filing bindings."""

    def __init__(self, item_id: str) -> None:
        self.item_id = item_id
        super().__init__(f"Item {item_id} has empty expected_bindings.accessions")


class MissingAccessionsError(ReproAccelerationError):
    """One or more accessions are absent from the bundle index."""

    def __init__(self, item_id: str, accessions: list[str]) -> None:
        self.item_id = item_id
        self.accessions = list(accessions)
        missing = ", ".join(accessions)
        super().__init__(f"Item {item_id} references accessions not in bundle: {missing}")


class TooManyIssuersError(ReproAccelerationError):
    """Item references more issuers than supported for a single subgraph slice."""

    def __init__(self, item_id: str, count: int, max_allowed: int = 4) -> None:
        self.item_id = item_id
        self.count = count
        self.max_allowed = max_allowed
        super().__init__(
            f"Item {item_id} references {count} issuers; maximum per item is {max_allowed}"
        )
