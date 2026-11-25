"""Checks that every lesson from session 2 onward is complete and consistent."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("torch", reason="lesson checks need PyTorch: make setup-lessons")

from course.manifest import load_course

SESSIONS = [s for s in load_course("lessons") if s.released and s.number >= 2]
IDS = [s.folder for s in SESSIONS]


def folder(s):
    return Path("lessons") / s.folder


def nodes(s):
    return [n for st in s.steps if st["kind"] == "exercise" for n in st["test"].split()]


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_shape_of_the_session(s):
    kinds = [st["kind"] for st in s.steps]
    assert {st["section"] for st in s.steps} == {"Pre-work", "Session", "Homework"}
    assert kinds.count("concept") == 3 and kinds.count("experiment") == 3
    assert kinds.count("problem") == 4 and kinds.count("review") == 5
    assert kinds.count("exercise") >= 3 and kinds.count("reading") >= 1
    assert sum(k == "video" and st["section"] == "Pre-work" for k, st in zip(kinds, s.steps)) >= 2
    assert 3 <= len(s.outcomes) <= 4


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_prework_video_is_20_to_60_minutes(s):
    minutes = sum(st["end"] - st["start"] for st in s.steps if st["kind"] == "video" and st["section"] == "Pre-work") / 60
    assert 20 <= minutes <= 60, minutes


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_files_exist_and_one_widget_is_used(s):
    for st in s.steps:
        if st["kind"] in ("concept", "exercise"):
            assert (folder(s) / st["file"]).is_file(), st["id"]
    widgets = list((folder(s) / "widgets").glob("*.js"))
    assert len(widgets) == 1
    pages = "".join((folder(s) / st["file"]).read_text() for st in s.steps if st["kind"] == "concept")
    assert f"/lessons-static/{s.folder}/widgets/{widgets[0].name}" in pages


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_every_lesson_test_is_assigned_and_collected(s):
    assigned = {n.split("::")[1] for n in nodes(s)}
    defined = set()
    for path in folder(s).glob("test_*.py"):
        defined |= set(re.findall(r"^def (test_\w+)", path.read_text(), re.M))
    assert assigned == defined
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *nodes(s)],
                         capture_output=True, text=True)
    assert out.returncode == 0 and f"{len(nodes(s))} tests collected" in out.stdout, out.stdout + out.stderr


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_learner_writes_at_most_60_lines_and_gaps_match_the_solution(s):
    learner = {st["file"] for st in s.steps if st["kind"] == "exercise"}
    total = 0
    for name in learner:
        solved = re.findall(r"# >>> YOUR CODE.*?\n(.*?)# <<< YOUR CODE", (folder(s) / "_solution" / name).read_text(), re.S)
        gaps = (folder(s) / name).read_text()
        assert gaps.count("raise NotImplementedError") == len(solved) == gaps.count("# <<< YOUR CODE")
        total += sum(len([l for l in g.strip().splitlines() if l.strip()]) for g in solved)
    assert 0 < total <= 60, total


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_solution_passes_and_unfilled_gaps_fail(s):
    run = lambda env: subprocess.run([sys.executable, "-m", "pytest", str(folder(s)), "-q", "-p", "no:cacheprovider"],
                                     capture_output=True, text=True, env={**os.environ, **env})
    solved = run({"LAB_SOLUTIONS": "1"})
    assert solved.returncode == 0, solved.stdout[-1500:]
    unsolved = run({"LAB_SOLUTIONS": "0"})
    assert unsolved.returncode != 0 and "NotImplementedError" in unsolved.stdout


@pytest.mark.parametrize("s", SESSIONS, ids=IDS)
def test_wording(s):
    text = "".join(p.read_text() for p in folder(s).rglob("*") if p.is_file() and p.suffix in {".py", ".html", ".yaml", ".js"})
    assert "{{" not in text  # no unfilled placeholders
