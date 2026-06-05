"""Report input/render errors for reproduction results viewer (014)."""

from __future__ import annotations

from pathlib import Path


class ReportInputError(Exception):
    """Required repro artifact missing or invalid."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        self.path = path.resolve() if path is not None else None
        detail = message
        if self.path is not None:
            detail = f"{message}: {self.path}"
        super().__init__(detail)


class ReportRenderError(Exception):
    """Report generation failed after inputs were loaded."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        self.path = path.resolve() if path is not None else None
        detail = message
        if self.path is not None:
            detail = f"{message}: {self.path}"
        super().__init__(detail)
