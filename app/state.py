"""In-memory status tracking for all configured checks."""
from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Dict

from .checks.base import CheckResult, CheckStatus


class StateStore:
    def __init__(self, check_names: list[str]) -> None:
        self._lock = asyncio.Lock()
        self._statuses: Dict[str, CheckStatus] = {name: CheckStatus.initial(name) for name in check_names}

    async def all_statuses(self) -> Dict[str, CheckStatus]:
        async with self._lock:
            return deepcopy(self._statuses)

    async def status_for(self, name: str) -> CheckStatus:
        async with self._lock:
            return deepcopy(self._statuses[name])

    async def update(self, name: str, result: CheckResult) -> CheckStatus:
        async with self._lock:
            status = self._statuses[name]
            updated = status.with_result(result)
            self._statuses[name] = updated
            return updated

