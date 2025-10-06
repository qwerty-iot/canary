"""Configuration loading for the Canary monitoring service."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import yaml


class ConfigurationError(Exception):
    """Raised when the configuration file is invalid."""


@dataclass(frozen=True)
class PushoverConfig:
    app_token: str
    user_key: str


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 8000
    title: str = "Canary Status"


@dataclass(frozen=True)
class CheckConfig:
    name: str
    type: str
    schedule: str
    options: Dict[str, Any]


@dataclass(frozen=True)
class AppConfig:
    pushover: PushoverConfig
    server: ServerConfig
    checks: List[CheckConfig]


def _require(section: Dict[str, Any], field: str) -> Any:
    if field not in section:
        raise ConfigurationError(f"Missing required field: {field}")
    return section[field]


def load_config(path: str | Path) -> AppConfig:
    """Load the YAML configuration file from *path*."""

    resolved_path = Path(path)
    if not resolved_path.is_file():
        raise ConfigurationError(f"Configuration file not found: {resolved_path}")

    with resolved_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration root must be a mapping")

    pushover_raw = raw.get("pushover")
    if not isinstance(pushover_raw, dict):
        raise ConfigurationError("pushover section must be provided")

    pushover = PushoverConfig(
        app_token=str(_require(pushover_raw, "app_token")),
        user_key=str(_require(pushover_raw, "user_key")),
    )

    server_raw = raw.get("server", {})
    if not isinstance(server_raw, dict):
        raise ConfigurationError("server section, if provided, must be a mapping")

    server = ServerConfig(
        host=str(server_raw.get("host", ServerConfig.host)),
        port=int(server_raw.get("port", ServerConfig.port)),
        title=str(server_raw.get("title", ServerConfig.title)),
    )

    checks_raw = raw.get("checks", [])
    if not isinstance(checks_raw, list) or not checks_raw:
        raise ConfigurationError("At least one check must be defined in the checks list")

    checks: List[CheckConfig] = []

    for entry in checks_raw:
        if not isinstance(entry, dict):
            raise ConfigurationError("Each check entry must be a mapping")

        name = str(_require(entry, "name"))
        check_type = str(_require(entry, "type"))
        schedule = str(_require(entry, "schedule"))
        options = entry.get("options", {})
        if not isinstance(options, dict):
            raise ConfigurationError(f"options for check {name} must be a mapping")

        checks.append(
            CheckConfig(
                name=name,
                type=check_type.lower(),
                schedule=schedule,
                options=options,
            )
        )

    return AppConfig(pushover=pushover, server=server, checks=checks)
