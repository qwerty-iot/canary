"""HTTP checker implementation."""
from __future__ import annotations

import json
from typing import Any, Tuple

import httpx

from .base import Check, CheckResult


class HttpCheck(Check):
    async def run(self) -> CheckResult:
        url = self.options.get("url")
        if not url:
            return CheckResult(ok=False, summary="Missing url option for HTTP check")

        method = str(self.options.get("method", "GET")).upper()
        expected_status = int(self.options.get("expected_status", 200))
        timeout = float(self.options.get("timeout", 10.0))
        expect_text = self.options.get("expect_text")
        expect_not_text = self.options.get("expect_not_text")
        include_body = self._coerce_bool(self.options.get("include_body_on_error", False))
        excerpt_length = int(self.options.get("response_excerpt_length", 500))

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.request(method, url)
            except httpx.HTTPError as exc:
                return CheckResult(ok=False, summary="HTTP request failed", details=str(exc))

        if response.status_code != expected_status:
            details = f"Expected {expected_status}, got {response.status_code}"
            body_snippet, body_format = self._response_snippet(response, include_body, excerpt_length)
            details_format = "text"
            if body_snippet:
                details = f"{details}\nResponse body:\n{body_snippet}"
                details_format = body_format
            return CheckResult(
                ok=False,
                summary="Unexpected HTTP status",
                details=details,
                details_format=details_format,
            )

        body_text = response.text
        if expect_text and expect_text not in body_text:
            details = f"Missing substring: {expect_text}"
            body_snippet, body_format = self._response_snippet(response, include_body, excerpt_length)
            details_format = "text"
            if body_snippet:
                details = f"{details}\nResponse body:\n{body_snippet}"
                details_format = body_format
            return CheckResult(
                ok=False,
                summary="Expected text not found",
                details=details,
                details_format=details_format,
            )
        if expect_not_text and expect_not_text in body_text:
            details = f"Unexpected substring: {expect_not_text}"
            body_snippet, body_format = self._response_snippet(response, include_body, excerpt_length)
            details_format = "text"
            if body_snippet:
                details = f"{details}\nResponse body:\n{body_snippet}"
                details_format = body_format
            return CheckResult(
                ok=False,
                summary="Forbidden text found",
                details=details,
                details_format=details_format,
            )

        return CheckResult(ok=True, summary="HTTP check passed")

    @staticmethod
    def _coerce_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "on"}
        return False

    def _response_snippet(
        self,
        response: httpx.Response,
        include_body: bool,
        excerpt_length: int,
    ) -> Tuple[str, str]:
        if not include_body:
            return "", "text"

        excerpt_length = max(0, excerpt_length)
        body_format = "text"

        body_text = response.text

        if self._looks_like_json(response):
            try:
                payload = response.json()
                formatted = json.dumps(payload, indent=2, ensure_ascii=False)
                body_format = "json"
                snippet = self._truncate(formatted, excerpt_length)
                return snippet, body_format
            except (ValueError, json.JSONDecodeError):
                pass

        snippet = self._truncate(body_text, excerpt_length)
        return snippet, body_format

    @staticmethod
    def _looks_like_json(response: httpx.Response) -> bool:
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type or "+json" in content_type:
            return True
        body = response.text.lstrip()
        return body.startswith("{") or body.startswith("[")

    @staticmethod
    def _truncate(text: str, limit: int) -> str:
        if limit and len(text) > limit:
            return text[:limit] + "…"
        return text
