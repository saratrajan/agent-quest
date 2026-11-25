"""The ticket store's JSON interface, shaped like ServiceNow's table API.

Incidents in the held-back set are served without their answers: those are
what the triage agent is scored against.
"""
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from servicedesk import db
from servicedesk.catalog import RUNBOOKS, SERVICES, SOURCES

INTERNAL = {"pattern_id", "is_vague", "split"}
ANSWERS = {"priority", "service", "assignment_group", "root_cause_category", "resolution", "resolved_at", "duplicate_of", "close_code"}
EVAL_FIELDS = ["number", "short_description", "description", "source", "opened_at", "priority_at_open"]
Source = Literal["monitoring", "customer-support", "synthetic-check", "employee", "partner"]
assert set(Source.__args__) == set(SOURCES)


class NewIncident(BaseModel):
    short_description: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=10000)
    source: Source


class NewNote(BaseModel):
    author: str = Field(min_length=1, max_length=100)
    role: str = Field(default="", max_length=100)
    text: str = Field(min_length=1, max_length=10000)


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class Tickets:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def conn(self) -> sqlite3.Connection:
        if not os.path.exists(self.db_path):
            raise HTTPException(503, "The incident data has not been generated yet. Run `make data` first.")
        return db.connect(self.db_path)

    def ready(self) -> bool:
        return os.path.exists(self.db_path)

    def public(self, row: sqlite3.Row, notes: list | None = None) -> dict:
        d = {k: row[k] for k in row.keys() if k not in INTERNAL}
        if row["split"] == "eval":
            d = {k: v for k, v in d.items() if k not in ANSWERS}
            d["state"] = "New"  # being resolved is part of the answer
        if notes is not None:
            d["work_notes"] = notes
        return d

    def list(self, split=("history", "live"), priority=None, service=None, source=None, q=None,
             opened_before=None, limit=20, offset=0) -> dict:
        where, args = [f"split IN ({', '.join('?' for _ in split)})"], list(split)
        for column, value in (("priority", priority), ("service", service), ("source", source)):
            if value is not None:
                where.append(f"{column} = ?")
                args.append(value)
        if q:
            pattern = "%" + q.lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            where.append("(lower(short_description) LIKE ? ESCAPE '\\' OR lower(description) LIKE ? ESCAPE '\\')")
            args += [pattern, pattern]
        if opened_before:
            where.append("opened_at < ?")
            args.append(opened_before)
        clause = " AND ".join(where)
        with self.conn() as c:
            total = c.execute(f"SELECT count(*) FROM incident WHERE {clause}", args).fetchone()[0]
            rows = c.execute(f"SELECT * FROM incident WHERE {clause} ORDER BY opened_at DESC, number DESC LIMIT ? OFFSET ?",
                             args + [min(limit, 100), offset]).fetchall()
        return {"result": [self.public(r) for r in rows], "total": total}

    def get(self, number: str) -> dict:
        with self.conn() as c:
            row = c.execute("SELECT * FROM incident WHERE number = ?", [number]).fetchone()
            if row is None:
                raise HTTPException(404, f"There is no incident {number}")
            only_api = " AND via_api = 1" if row["split"] == "eval" else ""
            notes = [dict(n) for n in c.execute(
                f"SELECT at, author, role, text FROM work_note WHERE number = ?{only_api} ORDER BY at, id", [number])]
        return self.public(row, notes)

    def split_of(self, number: str) -> str:
        with self.conn() as c:
            row = c.execute("SELECT split FROM incident WHERE number = ?", [number]).fetchone()
        if row is None:
            raise HTTPException(404, f"There is no incident {number}")
        return row["split"]

    def create(self, body: NewIncident) -> dict:
        with self.conn() as c:
            last = c.execute("SELECT max(number) FROM incident").fetchone()[0] or "INC0010000"
            number = f"INC{int(last[3:]) + 1:07d}"
            c.execute("INSERT INTO incident (number, short_description, description, source, opened_at, state, split) "
                      "VALUES (?, ?, ?, ?, ?, 'New', 'live')",
                      [number, body.short_description, body.description, body.source, _now()])
        return self.get(number)

    def add_note(self, number: str, body: NewNote) -> dict:
        self.split_of(number)
        note = {"at": _now(), "author": body.author, "role": body.role, "text": body.text}
        with self.conn() as c:
            c.execute("INSERT INTO work_note (number, at, author, role, text, via_api) VALUES (?, ?, ?, ?, ?, 1)",
                      [number, note["at"], note["author"], note["role"], note["text"]])
        return note

    def stats(self) -> dict:
        """Figures for the summary page, all computed from the stored incidents."""
        with self.conn() as c:
            one = lambda sql, *a: c.execute(sql, a).fetchone()[0]
            latest = one("SELECT max(opened_at) FROM incident")
            end = datetime.strptime(latest, "%Y-%m-%dT%H:%M:%SZ")
            d30 = (end - timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
            d60 = (end - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
            resolved = one("SELECT count(*) FROM incident WHERE split = 'history'")
            by_priority = {p: 0 for p in (1, 2, 3, 4)}
            for row in c.execute("SELECT priority_at_open AS p, count(*) AS n FROM incident "
                                 "WHERE split != 'history' AND priority_at_open IS NOT NULL GROUP BY 1"):
                by_priority[row["p"]] = row["n"]
            recent = c.execute("SELECT * FROM incident ORDER BY opened_at DESC, number DESC LIMIT 5").fetchall()
            return {
                "open": one("SELECT count(*) FROM incident WHERE split != 'history'"),
                "resolved": resolved,
                "avg_resolution_minutes": one("SELECT avg((julianday(resolved_at) - julianday(opened_at)) * 1440) "
                                              "FROM incident WHERE split = 'history'") or 0,
                "last_30_days": one("SELECT count(*) FROM incident WHERE opened_at > ?", d30),
                "prior_30_days": one("SELECT count(*) FROM incident WHERE opened_at > ? AND opened_at <= ?", d60, d30),
                "reprioritised_pct": round(100 * one("SELECT count(*) FROM incident WHERE split = 'history' "
                                                     "AND priority_at_open != priority") / resolved) if resolved else 0,
                "open_by_reported_priority": by_priority,
                "as_of": latest,
                "recent": [self.public(r) for r in recent],
            }

    def pattern_of(self, number: str) -> str | None:
        """The failure pattern behind a resolved incident; None until it has been triaged."""
        with self.conn() as c:
            row = c.execute("SELECT pattern_id FROM incident WHERE number = ? AND split = 'history'", [number]).fetchone()
        return row["pattern_id"] if row else None

    def related(self, number: str):
        """Duplicates of this incident, and others on the same service within a week.
        Nothing for an incident that has not been triaged: that would give the answer away."""
        with self.conn() as c:
            me = c.execute("SELECT * FROM incident WHERE number = ?", [number]).fetchone()
            if me is None:
                raise HTTPException(404, f"There is no incident {number}")
            if me["split"] != "history":
                return []
            rows = c.execute(
                "SELECT *, (duplicate_of = :n OR number = :parent) AS linked FROM incident "
                "WHERE split = 'history' AND number != :n AND (duplicate_of = :n OR number = :parent OR "
                "(service = :service AND abs(julianday(opened_at) - julianday(:opened)) <= 7)) "
                "ORDER BY linked DESC, abs(julianday(opened_at) - julianday(:opened)) LIMIT 8",
                {"n": number, "parent": me["duplicate_of"] or "", "service": me["service"], "opened": me["opened_at"]}).fetchall()
        return [{**self.public(r), "linked": bool(r["linked"])} for r in rows]

    def eval_list(self) -> dict:
        with self.conn() as c:
            rows = c.execute(f"SELECT {', '.join(EVAL_FIELDS)} FROM incident WHERE split = 'eval' ORDER BY opened_at").fetchall()
        return {"result": [dict(r) for r in rows], "total": len(rows)}

    def deploys(self, service: str, before: str | None = None, hours: int = 24) -> dict:
        before = before or _now()
        try:
            end = datetime.strptime(before, "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            raise HTTPException(422, "before must look like 2026-01-31T09:30:00Z")
        start = (end - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
        with self.conn() as c:
            rows = c.execute("SELECT * FROM deploy WHERE service = ? AND deployed_at > ? AND deployed_at <= ? "
                             "ORDER BY deployed_at DESC", [service, start, before]).fetchall()
        return {"result": [dict(r) for r in rows], "total": len(rows)}


def make_router(tickets: Tickets) -> APIRouter:
    r = APIRouter(prefix="/api")

    @r.get("/now/table/incident")
    def list_incidents(priority: int | None = Query(None, ge=1, le=4), service: str | None = None,
                       source: str | None = None, q: str | None = Query(None, max_length=200),
                       opened_before: str | None = None, limit: int = Query(20, ge=1), offset: int = Query(0, ge=0)):
        return tickets.list(priority=priority, service=service, source=source, q=q,
                            opened_before=opened_before, limit=limit, offset=offset)

    @r.get("/now/table/incident/{number}")
    def get_incident(number: str):
        return {"result": tickets.get(number)}

    @r.post("/now/table/incident", status_code=201)
    def create_incident(body: NewIncident):
        return {"result": tickets.create(body)}

    @r.post("/now/table/incident/{number}/work_notes", status_code=201)
    def add_note(number: str, body: NewNote):
        return {"result": tickets.add_note(number, body)}

    @r.get("/eval/incidents")
    def eval_incidents():
        return tickets.eval_list()

    @r.get("/services")
    def services():
        return {"result": [asdict(s) for s in SERVICES], "total": len(SERVICES)}

    @r.get("/services/{service_id}")
    def service(service_id: str):
        found = next((s for s in SERVICES if s.id == service_id), None)
        if found is None:
            raise HTTPException(404, f"There is no service '{service_id}'")
        return {"result": asdict(found)}

    @r.get("/runbooks")
    def runbooks(service: str | None = None):
        found = [{"id": b.id, "title": b.title, "service": b.service} for b in RUNBOOKS.values()
                 if service is None or b.service == service]
        return {"result": found, "total": len(found)}

    @r.get("/runbooks/{runbook_id}")
    def runbook(runbook_id: str):
        if runbook_id not in RUNBOOKS:
            raise HTTPException(404, f"There is no runbook '{runbook_id}'")
        return {"result": asdict(RUNBOOKS[runbook_id])}

    @r.get("/deploys")
    def deploys(service: str, before: str | None = None, hours: int = Query(24, ge=1, le=720)):
        return tickets.deploys(service, before, hours)

    return r
