"""HTML pages. Lesson text is escaped by the templates; only concept
fragments, which are part of the course material, are inserted as HTML."""
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from course.api import Course
from course.assistant import MILESTONES
from course.icons import LOCK_ICON, PHASE_ICONS, SESSION_ICONS
from course.manifest import SECTIONS

HERE = Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
templates.env.globals.update(session_icons=SESSION_ICONS, phase_icons=PHASE_ICONS, lock_icon=LOCK_ICON)
SERVED = {"concept", "widgets"}


def make_router(course: Course, desk_url: str) -> APIRouter:
    r = APIRouter()

    def page(request: Request, name: str, buddy: dict | None = None, **ctx) -> HTMLResponse:
        o = course.overview()
        if buddy is None:  # away from a lesson, Buddy offers questions about the whole course
            n = (o["continue"] or {}).get("session", 1)
            buddy = {"session": None, "nudge": False, "greeting": "Ask me about your progress or what comes next.",
                     "chips": [{"label": "What should I do next?", "ask": "What should I do next?"},
                               {"label": "My progress today", "ask": "How much progress have I logged today?"},
                               {"label": "Feedback so far", "ask": "What is the feedback from my learning so far?"},
                               {"label": f"What does session {n} teach?", "ask": f"What does session {n} teach?"}]}
        static_v = int(max(f.stat().st_mtime for f in (HERE / "static").iterdir() if f.is_file()))  # changes when any file does
        return templates.TemplateResponse(request, name, {"overall": o["overall"], "desk_url": desk_url, "buddy": buddy,
                                                         "static_v": static_v, **ctx})

    def plural(n: int, word: str) -> str:
        return f"{n} {word}" if n == 1 else f"{n} {word}s"

    def includes_of(steps: list[dict]) -> list[str]:
        names = [("video", "video"), ("reading", "reading"), ("concept", "concept page"), ("exercise", "coding exercise"),
                 ("experiment", "experiment"), ("problem", "problem"), ("review", "design review question")]
        out = [plural(n, word) for kind, word in names if (n := sum(st["kind"] == kind for st in steps))]
        minutes = round(sum(st["end"] - st["start"] for st in steps if st["kind"] == "video") / 60)
        return out + ([f"{minutes} min of video"] if minutes else [])

    def next_step(s: dict) -> str | None:
        return next((st["id"] for st in s["steps"] if not st["done"]), None)

    def steps_this_week() -> int:
        cutoff = datetime.now().astimezone() - timedelta(days=7)
        count = 0
        for entry in course.store.get()["steps"].values():
            try:
                recent = datetime.fromisoformat(entry.get("at", "")).astimezone() >= cutoff
            except ValueError:
                continue
            count += bool(entry.get("done") and recent)
        return count

    @r.get("/", response_class=HTMLResponse)
    def home(request: Request):
        o = course.overview()
        sessions = o["sessions"]
        current = (o["continue"] or {}).get("session")
        picks = [s for s in sessions if s["status"] in ("in-progress", "not-started", "locked")
                 and (current is None or s["number"] >= current)][:3]
        for s in picks:
            full = course.find(s["number"])
            s["includes"] = includes_of(full.steps)[-1:] if full else []
        counts = {"completed": sum(s["status"] == "done" for s in sessions),
                  "in-progress": sum(s["status"] == "in-progress" for s in sessions),
                  "not-started": sum(s["status"] in ("not-started", "locked") for s in sessions),
                  "not-built": sum(s["status"] == "not-released" for s in sessions)}
        status = {s["number"]: s["status"] for s in sessions}
        milestone = next(({"code": code, "name": name, "session": last} for code, name, last in MILESTONES
                          if not all(status[n] == "done" for n in range(1, last + 1))), None)
        total, done = o["overall"]["total"], o["overall"]["done"]
        streak = course.streak()
        paths = [{"name": phase, "blurb": blurb, "count": sum(s["phase"] == phase for s in sessions),
                  "built": sum(s["phase"] == phase and s["status"] != "not-released" for s in sessions)}
                 for phase, blurb in [("Fundamentals", "How a language model works, built by hand."),
                                      ("The agent", "Retrieval, tools, guardrails and measurement on the service desk.")]]
        return page(request, "home.html", nav="course", sessions=sessions, picks=picks, counts=counts, paths=paths,
                    pct=round(100 * done / total) if total else 0, milestone=milestone, week=steps_this_week(),
                    streak=f"{streak} {'day' if streak == 1 else 'days'}", **{"continue": o["continue"]})

    @r.get("/progress", response_class=HTMLResponse)
    def progress(request: Request):
        o = course.overview()
        total, done = o["overall"]["total"], o["overall"]["done"]
        rows = []
        for s in o["sessions"]:
            if s["status"] == "not-released":
                continue
            rows.append({**s, "pct": round(100 * s["done"] / s["total"]) if s["total"] else 0,
                         "next": None if s["status"] == "locked" else next_step(course.session(s["number"]))})
        return page(request, "progress.html", nav="progress", pct=round(100 * done / total) if total else 0,
                    streak=course.streak(), rows=rows, **{"continue": o["continue"]})

    @r.get("/sessions/{n}", response_class=HTMLResponse)
    def session(request: Request, n: int):
        found = course.find(n)
        if found is None:
            raise HTTPException(404, f"There is no session {n}")
        if not found.released:
            return page(request, "session.html", nav="course", released=False, s=found)
        if course.locked(n):
            return page(request, "session.html", nav="course", released=True, locked=True, s=found,
                        includes=includes_of(found.steps))
        s = course.session(n)
        folder = course.lessons_dir / s["folder"]
        for st in s["steps"]:
            if st["kind"] == "concept":
                path = folder / st["file"]
                st["html"] = path.read_text() if path.is_file() else "<p>This part of the lesson is missing.</p>"
        buddy = {"session": n, "greeting": "Need help with this session?",
                 "nudge": any(st["kind"] == "concept" and st["done"] for st in s["steps"]),
                 "chips": [{"label": f"Explain {s['title']}", "action": "explain"}, {"label": "Give me a hint", "action": "hint"},
                           {"label": "Show an example", "action": "example"}, {"label": "Quiz me", "action": "quiz"}]}
        return page(request, "session.html", buddy=buddy, nav="course", released=True, s=s, sections=SECTIONS,
                    includes=includes_of(s["steps"]), next=next_step(s) or s["steps"][0]["id"])

    @r.get("/results", response_class=HTMLResponse)
    def results(request: Request):
        return page(request, "results.html", nav="results", runs=course.results().get("runs", []))

    @r.get("/lessons-static/{folder}/{kind}/{name:path}")
    def lesson_file(folder: str, kind: str, name: str):
        base = (course.lessons_dir / folder / kind).resolve()
        target = (base / name).resolve()
        lessons = course.lessons_dir.resolve()
        if kind not in SERVED or base.parent.parent != lessons or not target.is_relative_to(base) or not target.is_file():
            raise HTTPException(404, "Not found")
        return FileResponse(target)

    return r
