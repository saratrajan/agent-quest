"""Checks on the real Session 1 material."""
import os
import re
import subprocess
import sys
from pathlib import Path

from course.checks import run_check
from course.manifest import load_course

L = Path("lessons/01-tokenization")
S1 = load_course("lessons")[0]


def test_session_has_all_three_sections_and_every_kind():
    assert {s["section"] for s in S1.steps} == {"Pre-work", "Session", "Homework"}
    assert {s["kind"] for s in S1.steps} == {"video", "reading", "concept", "exercise", "experiment", "problem", "review"}
    kinds = [s["kind"] for s in S1.steps]
    assert kinds.count("exercise") == 4 and kinds.count("experiment") == 3
    assert kinds.count("problem") == 4 and kinds.count("review") == 5


def test_referenced_files_exist():
    for s in S1.steps:
        if s["kind"] in ("concept", "exercise"):
            assert (L / s["file"]).is_file(), s["id"]


def test_every_exercise_test_is_collected():
    nodes = [n for s in S1.steps if s["kind"] == "exercise" for n in s["test"].split()]
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", *nodes],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert f"{len(nodes)} tests collected" in out.stdout


def test_all_eight_lesson_tests_are_assigned_to_a_step():
    nodes = {n.split("::")[1] for s in S1.steps if s["kind"] == "exercise" for n in s["test"].split()}
    defined = set(re.findall(r"^def (test_\w+)", (L / "test_bpe.py").read_text(), re.M))
    assert nodes == defined and len(defined) == 8


def test_learner_writes_at_most_60_lines():
    text = (L / "_solution" / "bpe.py").read_text()
    gaps = re.findall(r"# >>> YOUR CODE\n(.*?)# <<< YOUR CODE", text, re.S)
    assert len(gaps) == 4 and sum(len(g.strip().splitlines()) for g in gaps) <= 60


def test_gaps_are_unfilled_and_solution_passes():
    assert (L / "bpe.py").read_text().count("raise NotImplementedError") == 4
    env = {**os.environ, "LAB_SOLUTIONS": "1"}
    out = subprocess.run([sys.executable, "-m", "pytest", str(L), "-q", "-p", "no:cacheprovider"],
                         capture_output=True, text=True, env=env)
    assert "8 passed" in out.stdout, out.stdout


def test_a_step_with_two_tests_runs_both():
    step = next(s for s in S1.steps if s["id"] == "ex-train")
    assert len(step["test"].split()) == 2
    passed, output = run_check(step["test"], cwd=".")
    assert passed is False and "NotImplementedError" in output


def test_widget_uses_the_same_tie_break_as_python():
    js = (L / "widgets" / "bpe-stepper.js").read_text()
    assert "> best.count" in js and ">= best.count" not in js  # strictly greater: first pair seen wins a tie
