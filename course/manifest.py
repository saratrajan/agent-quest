"""Loads the course outline and each released session's steps."""
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REQUIRED = {
    "video": ["youtube_id", "start", "end", "channel", "watch_for"],
    "reading": ["url", "source", "note"],
    "concept": ["file"],
    "exercise": ["file", "test", "brief"],
    "experiment": ["prompt", "command"],
    "problem": ["prompt", "answer", "points"],
    "review": ["question", "model_answer"],
}
SECTIONS = ["Pre-work", "Session", "Homework"]


class ManifestError(ValueError):
    pass


@dataclass
class Session:
    number: int
    slug: str
    phase: str
    title: str
    summary: str
    released: bool = False
    steps: list[dict] = field(default_factory=list)
    notice: str = ""
    outcomes: list[str] = field(default_factory=list)

    @property
    def folder(self) -> str:
        return f"{self.number:02d}-{self.slug}"


def _load_steps(doc: dict, path: Path) -> list[dict]:
    steps = doc.get("steps") or []
    seen: set[str] = set()
    for i, step in enumerate(steps):
        where = f"{path}: step {i + 1}"
        for key in ("id", "kind", "title"):
            if key not in step:
                raise ManifestError(f"{where} is missing '{key}'")
        where = f"{path}: step '{step['id']}'"
        if step["kind"] not in REQUIRED:
            raise ManifestError(f"{where} has unknown kind '{step['kind']}'")
        if step["id"] in seen:
            raise ManifestError(f"{where} repeats an id already used in this session")
        seen.add(step["id"])
        for key in REQUIRED[step["kind"]]:
            if key not in step:
                raise ManifestError(f"{where} ({step['kind']}) is missing '{key}'")
        step.setdefault("section", "Session")
        if step["section"] not in SECTIONS:
            raise ManifestError(f"{where} has unknown section '{step['section']}'")
    return steps


def load_course(lessons_dir: str) -> list[Session]:
    root = Path(lessons_dir)
    outline = yaml.safe_load((root / "course.yaml").read_text())
    sessions = []
    for entry in outline:
        s = Session(entry["number"], entry["slug"], entry["phase"], entry["title"], entry["summary"])
        manifest = root / s.folder / "session.yaml"
        if manifest.exists():
            s.released = True
            doc = yaml.safe_load(manifest.read_text()) or {}
            s.steps = _load_steps(doc, manifest)
            s.notice = doc.get("notice", "")
            s.outcomes = list(doc.get("outcomes") or [])
        sessions.append(s)
    return sorted(sessions, key=lambda s: s.number)
