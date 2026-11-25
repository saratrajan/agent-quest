"""The Time Travel Inc. service desk: incidents, services and runbooks.
Start it with `make desk`.

It is a separate application from the course app (course/). The triage
agent talks to it over HTTP through the /api routes, like any other client.
"""
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from servicedesk.api import Tickets, make_router as make_api_router
from servicedesk.pages import make_router as make_pages_router

HERE = Path(__file__).parent


def create_app(db_path: str | None = None) -> FastAPI:
    app = FastAPI(title="Time Travel Inc. Service Desk")
    tickets = Tickets(db_path or os.environ.get("SERVICE_DESK_DB", "data/timetravel.db"))
    app.include_router(make_api_router(tickets))
    app.include_router(make_pages_router(tickets))
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    return app


app = create_app()
