"""The service desk's own pages: queues, an incident record, new incident,
services and runbooks. All text from tickets is escaped by the templates."""
import math
from pathlib import Path
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from servicedesk.api import NewIncident, NewNote, Tickets
from servicedesk.catalog import PATTERNS, RUNBOOKS, SERVICES, SOURCES

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
PAGE_SIZE = 25
VIEWS = {"open": ("eval", "live"), "resolved": ("history",), "all": ("history", "eval", "live")}
TABS = {"overview": "Overview", "timeline": "Timeline", "related": "Related incidents",
        "services": "Affected services", "knowledge": "Knowledge"}
FIELD_NAMES = {"short_description": "short description", "description": "description", "source": "source",
               "author": "your name", "text": "note"}


async def form_of(request: Request) -> dict:
    body = (await request.body()).decode("utf-8", errors="replace")
    return {k: v[0].strip() for k, v in parse_qs(body, keep_blank_values=True).items()}


def problems(err: ValidationError) -> list[str]:
    return [f"Check the {FIELD_NAMES.get(str(e['loc'][0]), e['loc'][0])}: {e['msg'].lower()}." for e in err.errors()]


def make_router(tickets: Tickets) -> APIRouter:
    r = APIRouter()

    def page(request: Request, name: str, status: int = 200, **ctx) -> HTMLResponse:
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    @r.get("/", response_class=HTMLResponse)
    def home(request: Request):
        if not tickets.ready():
            return page(request, "home.html", nav="home", ready=False)
        s = tickets.stats()
        total = sum(s["open_by_reported_priority"].values()) or 1
        ring, start, donut = 2 * math.pi * 42, 0.0, []
        for p in (1, 2, 3, 4):
            n = s["open_by_reported_priority"][p]
            length = ring * n / total
            donut.append({"priority": p, "count": n, "dash": f"{length:.2f} {ring - length:.2f}", "offset": f"{-start:.2f}"})
            start += length
        m = round(s["avg_resolution_minutes"])
        change = None
        if s["prior_30_days"]:
            change = round(100 * (s["last_30_days"] - s["prior_30_days"]) / s["prior_30_days"])
        return page(request, "home.html", nav="home", ready=True, s=s, donut=donut, change=change,
                    avg=f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m")

    @r.get("/incidents", response_class=HTMLResponse)
    def incidents(request: Request, view: str = "open", q: str | None = Query(None, max_length=200),
                  priority: str | None = None, service: str | None = None, source: str | None = None,
                  page_no: int = Query(1, ge=1, alias="page")):
        view = view if view in VIEWS else "open"
        if not tickets.ready():
            return page(request, "incidents.html", nav="incidents", view=view, ready=False)
        f = {"q": q or None, "priority": int(priority) if priority in {"1", "2", "3", "4"} else None,
             "service": service or None, "source": source or None}
        if view == "open":
            f["priority"] = f["service"] = None  # not yet triaged, so there is nothing to filter on
        got = tickets.list(split=VIEWS[view], limit=PAGE_SIZE, offset=(page_no - 1) * PAGE_SIZE, **f)

        def link(n: int) -> str:
            return "/incidents?" + urlencode({"view": view, **{k: v for k, v in f.items() if v is not None}, "page": n})

        return page(request, "incidents.html", nav="incidents", view=view, ready=True, f=f, rows=got["result"],
                    total=got["total"], page=page_no, pages=max(1, -(-got["total"] // PAGE_SIZE)), link=link,
                    services=SERVICES, sources=SOURCES)

    @r.get("/incidents/new", response_class=HTMLResponse)
    def new_incident(request: Request):
        return page(request, "new.html", nav="new", sources=SOURCES, values={}, errors=[])

    @r.post("/incidents/new")
    async def create_incident(request: Request):
        values = await form_of(request)
        try:
            body = NewIncident(**{k: values.get(k, "") for k in ("short_description", "description", "source")})
        except ValidationError as err:
            return page(request, "new.html", 422, nav="new", sources=SOURCES, values=values, errors=problems(err))
        created = tickets.create(body)
        return RedirectResponse(f"/incidents/{created['number']}", status_code=303)

    def steps_of(i: dict) -> list[dict]:
        notes = i["work_notes"]
        resolved = i["state"] == "Resolved"
        first = next((n["at"] for n in notes if "on-call" in n.get("role", "")), notes[0]["at"] if notes else None)
        fix = next((n["at"] for n in notes if n["text"].startswith(("Applying the fix", "Linked as a duplicate"))), None)
        return [{"name": "Logged", "at": i["opened_at"], "done": True},
                {"name": "Investigating", "at": first, "done": bool(notes)},
                {"name": "Fix applied", "at": fix if resolved else None, "done": resolved},
                {"name": "Resolved", "at": i.get("resolved_at"), "done": resolved}]

    def record(request: Request, number: str, tab: str = "overview", status: int = 200, errors=(), draft=None) -> HTMLResponse:
        i = tickets.get(number)
        tab = tab if tab in TABS else "overview"
        triaged = bool(i.get("service"))
        service = next((s for s in SERVICES if s.id == i.get("service")), None)
        books = [rb for rb in RUNBOOKS.values() if triaged and (
            rb.service == i["service"] or any(p.runbook == rb.id and p.service == i["service"] for p in PATTERNS))]
        fits = next((p.runbook for p in PATTERNS if p.id == tickets.pattern_of(number)), None)
        books.sort(key=lambda rb: rb.id != fits)  # the one that fits this incident first
        best = [rb for rb in books if rb.id == fits]
        return page(request, "incident.html", status, nav="incidents", i=i, tab=tab, tabs=TABS, triaged=triaged, best=best,
                    deploys=tickets.deploys(i["service"], i["opened_at"], 2)["result"] if triaged else [],
                    service=service, books=books, related=tickets.related(number) if tab == "related" else [],
                    steps=steps_of(i), errors=list(errors), draft=draft or {})

    @r.get("/incidents/{number}", response_class=HTMLResponse)
    def incident(request: Request, number: str, tab: str = "overview"):
        return record(request, number, tab)

    @r.post("/incidents/{number}/notes")
    async def add_note(request: Request, number: str):
        tickets.split_of(number)  # 404 before anything else
        values = await form_of(request)
        try:
            body = NewNote(author=values.get("author", ""), text=values.get("text", ""))
        except ValidationError as err:
            return record(request, number, "timeline", 422, problems(err), values)
        tickets.add_note(number, body)
        return RedirectResponse(f"/incidents/{number}", status_code=303)

    @r.get("/services", response_class=HTMLResponse)
    def services(request: Request):
        books = {}
        for rb in RUNBOOKS.values():
            books.setdefault(rb.service, []).append(rb)
        return page(request, "services.html", nav="knowledge", services=SERVICES, books=books)

    @r.get("/runbooks/{runbook_id}", response_class=HTMLResponse)
    def runbook(request: Request, runbook_id: str):
        if runbook_id not in RUNBOOKS:
            raise HTTPException(404, f"There is no runbook '{runbook_id}'")
        return page(request, "runbook.html", nav="knowledge", rb=RUNBOOKS[runbook_id])

    return r
