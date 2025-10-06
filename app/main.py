"""Entry point for the Canary monitoring service."""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import List

import uvicorn
from fastapi import FastAPI

from .checks import create_check
from .config import AppConfig, CheckConfig, load_config
from .pushover import PushoverClient
from .scheduler import ScheduledCheck, Scheduler
from .state import StateStore
from .web import create_web_app

LOGGER = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Canary monitoring service")
    default_path = os.getenv("CANARY_CONFIG", "config.yaml")
    parser.add_argument(
        "--config",
        default=default_path,
        help="Path to the YAML configuration file (default: env CANARY_CONFIG or config.yaml)",
    )
    return parser.parse_args()


def build_scheduled_checks(check_configs: List[CheckConfig]) -> List[ScheduledCheck]:
    scheduled: List[ScheduledCheck] = []
    for config in check_configs:
        check = create_check(config.type, config.name, config.options)
        scheduled.append(ScheduledCheck(config=config, instance=check))
    return scheduled


async def run_service(app_config: AppConfig) -> None:
    state = StateStore([check.name for check in app_config.checks])
    pushover = PushoverClient(app_config.pushover)
    scheduled_checks = build_scheduled_checks(app_config.checks)
    scheduler = Scheduler(scheduled_checks, state, pushover)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        LOGGER.info("Service startup: sending ready notification and starting scheduler")
        await pushover.send(message="🚀 Canary monitor has started", title="Canary Ready")
        await scheduler.start()
        try:
            yield
        finally:
            LOGGER.info("Service shutting down: stopping scheduler")
            await scheduler.stop()
            await pushover.close()

    fastapi_app = create_web_app(state, lifespan_handler=lifespan, page_title=app_config.server.title)

    server_config = uvicorn.Config(
        fastapi_app,
        host=app_config.server.host,
        port=app_config.server.port,
        log_level="info",
    )
    server = uvicorn.Server(server_config)
    await server.serve()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    args = parse_args()
    try:
        app_config = load_config(args.config)
    except Exception as exc:  # pylint: disable=broad-except
        LOGGER.error("Failed to load configuration: %s", exc)
        raise SystemExit(2) from exc

    asyncio.run(run_service(app_config))


if __name__ == "__main__":
    main()
