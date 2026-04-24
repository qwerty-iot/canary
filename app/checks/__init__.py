"""Factories for creating configured checks."""
from __future__ import annotations

from typing import Dict, Type

from .base import Check
from .http import HttpCheck
from .azure import AzureAppRegistrationCheck

CHECK_TYPES: Dict[str, Type[Check]] = {
    "http": HttpCheck,
    "azure_app_registrations": AzureAppRegistrationCheck,
}


def create_check(check_type: str, name: str, options: dict) -> Check:
    try:
        check_cls = CHECK_TYPES[check_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported check type: {check_type}") from exc
    return check_cls(name=name, options=options)
