"""Azure App Registration secret expiry checker."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Sequence

import httpx
from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential

from .base import Check, CheckResult

GRAPH_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0/applications?$select=displayName,appId,passwordCredentials"


class AzureAppRegistrationCheck(Check):
    async def run(self) -> CheckResult:
        tenant_id = self.options.get("tenant_id")
        client_id = self.options.get("client_id")
        client_secret = self.options.get("client_secret")
        filter_prefixes = self._normalize_list(self.options.get("include_prefixes"))
        exclude_prefixes = self._normalize_list(self.options.get("exclude_prefixes"))
        ignore_apps = self._normalize_list(self.options.get("exclude_apps"))

        if not tenant_id:
            return CheckResult(
                ok=False,
                summary="Missing tenant_id for Azure app registration check",
                severity="error",
            )

        credential = await self._create_credential(tenant_id, client_id, client_secret)
        if credential is None:
            return CheckResult(
                ok=False,
                summary="Unable to create Azure credential",
                severity="error",
            )

        try:
            token = await credential.get_token(GRAPH_SCOPE)
        except Exception as exc:  # pylint: disable=broad-except
            await credential.close()
            return CheckResult(
                ok=False,
                summary="Failed to obtain Graph token",
                details=str(exc),
                severity="error",
            )

        headers = {"Authorization": f"Bearer {token.token}", "Accept": "application/json"}
        now = datetime.now(timezone.utc)
        critical_cutoff = now + timedelta(hours=48)
        warning_cutoff = now + timedelta(days=30)

        warnings: List[str] = []
        criticals: List[str] = []

        try:
            async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
                next_link: str | None = GRAPH_ENDPOINT
                while next_link:
                    response = await client.get(next_link)
                    response.raise_for_status()
                    payload = response.json()
                    values = payload.get("value", [])

                    for app in values:
                        name = app.get("displayName") or app.get("appId")
                        if not name:
                            continue
                        if ignore_apps and name in ignore_apps:
                            continue
                        if filter_prefixes and not any(name.startswith(prefix) for prefix in filter_prefixes):
                            continue
                        if exclude_prefixes and any(name.startswith(prefix) for prefix in exclude_prefixes):
                            continue

                        for secret in app.get("passwordCredentials", []):
                            display = secret.get("displayName", "default")
                            expires_on = secret.get("endDateTime") or secret.get("expiryDateTime")
                            if not expires_on:
                                continue
                            expiry = self._parse_datetime(expires_on)
                            if expiry is None:
                                continue
                            if expiry <= now:
                                criticals.append(
                                    f"{name} / {display}: expired {self._format_delta(now - expiry)} ago"
                                )
                            elif expiry <= critical_cutoff:
                                criticals.append(
                                    f"{name} / {display}: expires in {self._format_delta(expiry - now)}"
                                )
                            elif expiry <= warning_cutoff:
                                warnings.append(
                                    f"{name} / {display}: expires in {self._format_delta(expiry - now)}"
                                )

                    next_link = payload.get("@odata.nextLink")
        except httpx.HTTPError as exc:
            await credential.close()
            return CheckResult(
                ok=False,
                summary="Failed to query Microsoft Graph",
                details=str(exc),
                severity="error",
            )

        await credential.close()

        if criticals:
            details = "\n".join(criticals + warnings)
            return CheckResult(
                ok=False,
                summary=f"{len(criticals)} app secrets expiring imminently",
                details=details,
                severity="error",
            )
        if warnings:
            details = "\n".join(warnings)
            return CheckResult(
                ok=False,
                summary=f"{len(warnings)} app secrets expiring within 30 days",
                details=details,
                severity="warning",
            )
        return CheckResult(ok=True, summary="All app registration secrets healthy", severity="ok")

    @staticmethod
    async def _create_credential(
        tenant_id: str,
        client_id: str | None,
        client_secret: str | None,
    ) -> DefaultAzureCredential | ClientSecretCredential | None:
        try:
            if client_id and client_secret:
                return ClientSecretCredential(
                    tenant_id=tenant_id,
                    client_id=client_id,
                    client_secret=client_secret,
                )
            return DefaultAzureCredential(
                exclude_shared_token_cache_credential=True,
                tenant_id=tenant_id,
            )
        except Exception:  # pylint: disable=broad-except
            return None

    @staticmethod
    def _parse_datetime(raw: str) -> datetime | None:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError:
            return None

    @staticmethod
    def _format_delta(delta: timedelta) -> str:
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            total_seconds = 0
        days, rem = divmod(total_seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        parts: List[str] = []
        if days:
            parts.append(f"{days}d")
        if hours:
            parts.append(f"{hours}h")
        if minutes:
            parts.append(f"{minutes}m")
        return " ".join(parts) or "0m"

    @staticmethod
    def _normalize_list(value: Sequence[str] | str | None) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return [str(item) for item in value if item]
