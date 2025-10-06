"""Integration helper for Pushover notifications."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

from .config import PushoverConfig

LOGGER = logging.getLogger(__name__)

PUSHOVER_ENDPOINT = "https://api.pushover.net/1/messages.json"


class PushoverClient:
    def __init__(self, config: PushoverConfig) -> None:
        self._config = config
        self._client = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._client.aclose()

    async def send(
        self,
        message: str,
        title: str = "Canary",
        priority: int = 0,
        url: Optional[str] = None,
        url_title: Optional[str] = None,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload: Dict[str, Any] = {
            "token": self._config.app_token,
            "user": self._config.user_key,
            "message": message,
            "title": title,
            "priority": priority,
        }
        if url:
            payload["url"] = url
        if url_title:
            payload["url_title"] = url_title
        if additional_params:
            payload.update(additional_params)

        try:
            response = await self._client.post(PUSHOVER_ENDPOINT, data=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            LOGGER.error("Pushover error %s: %s", exc.response.status_code, exc.response.text)
        except httpx.HTTPError as exc:
            LOGGER.error("Pushover request failed: %s", exc)

