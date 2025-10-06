"""Abstract base classes and utilities for check implementations."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class CheckResult:
    ok: bool
    summary: str
    details: Optional[str] = None
    details_format: str = "text"


class Check(ABC):
    """Base class for all service health checks."""

    def __init__(self, name: str, options: Dict[str, Any]):
        self.name = name
        self.options = options

    @abstractmethod
    async def run(self) -> CheckResult:
        """Execute the check and return the result."""


@dataclass
class CheckStatus:
    name: str
    ok: Optional[bool]
    summary: str
    details: Optional[str]
    details_format: str
    last_run: Optional[datetime]
    last_changed: Optional[datetime]

    @classmethod
    def initial(cls, name: str) -> "CheckStatus":
        return cls(
            name=name,
            ok=None,
            summary="Pending",
            details=None,
            details_format="text",
            last_run=None,
            last_changed=None,
        )

    def with_result(self, result: CheckResult) -> "CheckStatus":
        now = datetime.now(timezone.utc)
        last_changed = self.last_changed
        if self.ok != result.ok:
            last_changed = now
        return CheckStatus(
            name=self.name,
            ok=result.ok,
            summary=result.summary,
            details=result.details,
            details_format=result.details_format,
            last_run=now,
            last_changed=last_changed or now,
        )
