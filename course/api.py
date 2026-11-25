"""JSON interface for the course: outline, session steps, progress."""
import json
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from course import checks
from course.manifest import Session, load_course
from datetime import date

from course.progress import ProgressStore, streak, summarise

ANSWERABLE = {"experiment", "problem", "review"}


class CompleteBody(BaseModel):
    done: bool
    source: Literal["manual", "auto"] = "manual"


class AnswerBody(BaseModel):
    text: str = Field(max_length=20000)


class MarkBody(BaseModel):
    points: int = Field(ge=0)


class Turn(BaseModel):
    role: Literal["you", "buddy"]
    text: str = Field(max_length=4000)


class QuizRef(BaseModel):
    question: str = Field(max_length=1000)
    session: int
    step_id: str = Field(max_length=100)
    chunk: int = Field(ge=0)


class AssistantBody(BaseModel):
    message: str = Field(max_length=2000)
    session: int | None = None
    action: Literal["explain", "hint", "example", "quiz"] | None = None
    history: list[Turn] = Field(default_factory=list, max_length=12)
    quiz: QuizRef | None = None


class Course:
    """Everything the routes and pages need, reading files fresh each time so
    lesson edits show up without a restart."""

    def __init__(self, data_dir: str, lessons_dir: str, unlock_all: bool = False):
        self.unlock_all = unlock_all
        self.data_dir = Path(data_dir)
        self.lessons_dir = Path(lessons_dir)
        self.root = self.lessons_dir.resolve().parent
        self.store = ProgressStore(self.data_dir / "progress.json")

    def sessions(self) -> list[Session]:
        return load_course(str(self.lessons_dir))

    def overview(self) -> dict:
        sessions = self.sessions()
        summary = summarise(sessions, self.store.get(), self.unlock_all)
        return {
            "sessions": [
                {"number": s.number, "slug": s.slug, "phase": s.phase, "title": s.title,
                 "summary": s.summary, **summary["sessions"][s.number]}
                for s in sessions
            ],
            "overall": summary["overall"],
            "continue": summary["continue"],
        }

    def streak(self) -> int:
        return streak(self.store.get(), date.today())

    def locked(self, number: int) -> bool:
        status = summarise(self.sessions(), self.store.get(), self.unlock_all)["sessions"].get(number, {}).get("status")
        return status == "locked"

    def find(self, number: int) -> Session | None:
        return next((s for s in self.sessions() if s.number == number), None)

    def session(self, number: int) -> dict:
        s = self.find(number)
        if s is None:
            raise HTTPException(404, f"There is no session {number}")
        if not s.released:
            raise HTTPException(404, f"Session {number} is not yet released")
        if self.locked(number):
            raise HTTPException(423, f"Session {number} is locked. Finish session {number - 1} to unlock it.")
        state = self.store.get()
        steps = []
        for st in s.steps:
            key = f"{number}/{st['id']}"
            merged = {**st, "done": bool(state["steps"].get(key, {}).get("done")),
                      "answer": state["answers"].get(key, ""), "check": state["checks"].get(key)}
            if st["kind"] == "problem":
                merged["answer_key"] = st["answer"]  # the worked answer; "answer" is the learner's
                merged["mark"] = state["marks"].get(key, {}).get("points")
            steps.append(merged)
        done = sum(st["done"] for st in steps)
        return {"number": s.number, "slug": s.slug, "folder": s.folder, "phase": s.phase,
                "title": s.title, "summary": s.summary, "notice": s.notice, "outcomes": s.outcomes, "steps": steps, "done": done, "total": len(steps)}

    def step(self, number: int, step_id: str) -> dict:
        for st in self.session(number)["steps"]:
            if st["id"] == step_id:
                return st
        raise HTTPException(404, f"Session {number} has no step '{step_id}'")

    def results(self) -> dict:
        path = self.data_dir / "results.json"
        if not path.exists():
            return {"runs": []}
        try:
            return json.loads(path.read_text())
        except ValueError:
            return {"runs": []}


def saved_runs(data_dir: Path) -> list[dict]:
    """Training runs written by the lessons, newest first. Unreadable files are skipped."""
    runs = []
    for path in sorted((data_dir / "runs").glob("*.json")):
        try:
            record = json.loads(path.read_text())
        except (ValueError, OSError):
            continue
        if isinstance(record, dict):
            runs.append(record)
    return sorted(runs, key=lambda r: str(r.get("saved_at", "")), reverse=True)


def make_router(course: Course, assistant) -> APIRouter:
    r = APIRouter(prefix="/api/course")

    @r.get("")
    def overview():
        return course.overview()

    @r.get("/results")
    def results():
        return course.results()

    @r.post("/assistant")
    def ask_assistant(body: AssistantBody):
        return assistant.reply(body.message, body.session, body.action, [t.model_dump() for t in body.history],
                               body.quiz.model_dump() if body.quiz else None)

    @r.post("/sessions/{n}/steps/{step_id}/mark")
    def mark(n: int, step_id: str, body: MarkBody):
        st = course.step(n, step_id)
        if st["kind"] != "problem":
            raise HTTPException(409, "Only problems are marked")
        if body.points > st["points"]:
            raise HTTPException(422, f"This problem is worth {st['points']} points")
        course.store.set_mark(n, step_id, body.points)
        return {"points": body.points}

    @r.get("/runs")
    def runs():
        return {"runs": saved_runs(course.data_dir)}

    @r.get("/sessions/{n}")
    def session(n: int):
        return course.session(n)

    @r.post("/sessions/{n}/steps/{step_id}/complete")
    def complete(n: int, step_id: str, body: CompleteBody):
        st = course.step(n, step_id)
        if st["kind"] == "exercise":
            raise HTTPException(409, "Exercises complete when their tests pass")
        course.store.set_done(n, step_id, body.done, body.source)
        return {"done": body.done}

    @r.post("/sessions/{n}/steps/{step_id}/answer")
    def answer(n: int, step_id: str, body: AnswerBody):
        st = course.step(n, step_id)
        if st["kind"] not in ANSWERABLE:
            raise HTTPException(409, "This step does not take a written answer")
        course.store.set_answer(n, step_id, body.text)
        return {"saved": True}

    @r.post("/sessions/{n}/steps/{step_id}/check")
    def check(n: int, step_id: str):
        st = course.step(n, step_id)
        if st["kind"] != "exercise":
            raise HTTPException(409, "Only exercises have tests to run")
        passed, output = checks.run_check(st["test"], cwd=str(course.root))
        course.store.set_check(n, step_id, passed, output)
        course.store.set_done(n, step_id, passed, "tests")
        return {"passed": passed, "output": output}

    return r
