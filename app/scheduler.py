"""Scheduling loop for executing checks based on cron expressions."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable

from croniter import croniter

from .checks.base import Check, CheckResult
from .config import CheckConfig
from .pushover import PushoverClient
from .state import StateStore

LOGGER = logging.getLogger(__name__)


@dataclass
class ScheduledCheck:
    config: CheckConfig
    instance: Check
    next_run: datetime = field(init=False)
    previous_ok: bool | None = field(init=False, default=None)
    previous_severity: str | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        now = datetime.now(timezone.utc)
        self._cron = croniter(self.config.schedule, now)
        # Schedule the first execution according to cron pattern
        self.next_run = self._cron.get_next(datetime)

    def advance(self) -> None:
        self.next_run = self._cron.get_next(datetime)


class Scheduler:
    def __init__(self, checks: Iterable[ScheduledCheck], state: StateStore, pushover: PushoverClient) -> None:
        self._checks = list(checks)
        self._state = state
        self._pushover = pushover
        self._tasks: list[asyncio.Task[None]] = []
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        for scheduled in self._checks:
            task = asyncio.create_task(self._run_check_loop(scheduled), name=f"check:{scheduled.config.name}")
            self._tasks.append(task)
        LOGGER.info("Scheduler started for %s checks", len(self._checks))

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        LOGGER.info("Scheduler stopped")

    async def _run_check_loop(self, scheduled: ScheduledCheck) -> None:
        while self._running:
            delay = self._seconds_until(scheduled.next_run)
            if delay > 0:
                try:
                    await asyncio.sleep(delay)
                except asyncio.CancelledError:
                    raise

            LOGGER.debug("Running check %s", scheduled.config.name)
            result = await self._invoke_check(scheduled.instance)
            status = await self._state.update(scheduled.config.name, result)

            await self._handle_notification(scheduled, result, status.summary)

            scheduled.advance()

    async def _invoke_check(self, check: Check) -> CheckResult:
        try:
            return await check.run()
        except Exception as exc:  # pylint: disable=broad-except
            LOGGER.exception("Unhandled exception while running check %s", check.name)
            return CheckResult(ok=False, summary="Check crashed", details=str(exc), severity="error")

    async def _handle_notification(self, scheduled: ScheduledCheck, result: CheckResult, summary: str) -> None:
        previous_ok = scheduled.previous_ok
        previous_severity = scheduled.previous_severity
        scheduled.previous_ok = result.ok
        scheduled.previous_severity = result.severity

        if result.severity == "ok":
            if previous_severity in {"warning", "error"}:
                await self._pushover.send(
                    message=f"✅ {scheduled.config.name} has recovered",
                    title="Canary Recovery",
                )
            return

        if result.severity == "warning":
            if previous_severity != "warning":
                detail = ""
                if result.details:
                    detail = f"\n{result.details}" if (result.details_format == "json" or "\n" in result.details) else f" ({result.details})"
                await self._pushover.send(
                    message=f"⚠️ {scheduled.config.name} warning: {summary}{detail}",
                    title="Canary Warning",
                    priority=0,
                )
            return

        if result.severity == "error":
            if previous_severity != "error" or previous_ok is not False:
                detail = ""
                if result.details:
                    detail = f"\n{result.details}" if (result.details_format == "json" or "\n" in result.details) else f" ({result.details})"
                await self._pushover.send(
                    message=f"🚨 {scheduled.config.name} is failing: {summary}{detail}",
                    title="Canary Alert",
                    priority=1,
                )

    @staticmethod
    def _seconds_until(next_run: datetime) -> float:
        now = datetime.now(timezone.utc)
        delta = (next_run - now).total_seconds()
        return max(0.0, delta)
