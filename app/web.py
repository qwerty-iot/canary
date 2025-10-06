"""HTTP interface for surfacing check status."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import AsyncIterator, Callable, Dict, Optional

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from .checks.base import CheckStatus
from .state import StateStore

TEMPLATE_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"

def _serialize_status(status: CheckStatus) -> Dict[str, object]:
    def fmt(dt: datetime | None) -> str | None:
        return dt.isoformat() if dt else None

    return {
        "name": status.name,
        "ok": status.ok,
        "summary": status.summary,
        "details": status.details,
        "details_format": status.details_format,
        "last_run": fmt(status.last_run),
        "last_changed": fmt(status.last_changed),
    }


LifespanHandler = Callable[[FastAPI], AsyncIterator[None]]


def create_web_app(
    state: StateStore,
    lifespan_handler: Optional[LifespanHandler] = None,
    page_title: str = "Canary Status",
) -> FastAPI:
    app = FastAPI(title=page_title, version="0.1.0", lifespan=lifespan_handler)
    templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        statuses = await state.all_statuses()
        items = []
        for status in statuses.values():
            items.append(
                {
                    **_serialize_status(status),
                    "status_text": "OK" if status.ok else ("Failing" if status.ok is False else "Pending"),
                    "status_class": "ok" if status.ok else ("failing" if status.ok is False else "pending"),
                    "details_is_json": status.details_format == "json",
                }
            )
        return templates.TemplateResponse(
            "status.html",
            {"request": request, "checks": items, "page_title": page_title, "repo_url": "https://github.com/qwerty-iot/canary"},
        )

    @app.get("/status")
    async def status_endpoint() -> Dict[str, object]:
        statuses = await state.all_statuses()
        payload = [_serialize_status(entry) for entry in statuses.values()]
        return {"checks": jsonable_encoder(payload), "title": page_title}

    return app
