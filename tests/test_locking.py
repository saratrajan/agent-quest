"""A session stays locked until the one before it is complete."""
import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import STEPS
from course.app import create_app

S1_MANUAL = ["v1", "r1", "c1", "exp1", "p1", "q1"]


@pytest.fixture
def root(lab_root):
    s2 = lab_root / "lessons" / "02-next-token"
    s2.mkdir()
    steps = [dict(s, id="a1") for s in STEPS[:1]] + [dict(STEPS[1], id="a2")]
    (s2 / "session.yaml").write_text(yaml.safe_dump({"steps": steps, "outcomes": ["Train a model"]}))
    return lab_root


def app(root, **kw):
    return TestClient(create_app(data_dir=str(root / "data"), lessons_dir=str(root / "lessons"), **kw))


def finish_session_1(c):
    for sid in S1_MANUAL:
        c.post(f"/api/course/sessions/1/steps/{sid}/complete", json={"done": True})
    assert c.post("/api/course/sessions/1/steps/ex1/check").json()["passed"]


def status(c, n):
    return c.get("/api/course").json()["sessions"][n - 1]["status"]


def test_next_session_is_locked_until_the_previous_one_is_done(root):
    c = app(root)
    assert status(c, 1) == "not-started" and status(c, 2) == "locked" and status(c, 3) == "not-released"
    finish_session_1(c)
    assert status(c, 1) == "done" and status(c, 2) == "not-started"


def test_locked_session_refuses_its_steps(root):
    c = app(root)
    r = c.get("/api/course/sessions/2")
    assert r.status_code == 423 and "session 1" in r.json()["detail"]
    assert c.post("/api/course/sessions/2/steps/a1/complete", json={"done": True}).status_code == 423
    assert c.get("/api/course").json()["overall"] == {"done": 0, "total": 9}


def test_locked_session_page_previews_but_shows_no_steps(root):
    h = app(root).get("/sessions/2").text
    assert "Locked" in h and 'href="/sessions/1"' in h and "Train a model" in h
    assert "<article" not in h and "abc123XYZ_-" not in h


def test_home_and_progress_mark_the_locked_session(root):
    c = app(root)
    assert 'data-status="locked"' in c.get("/").text and "Finish session 1 to unlock" in c.get("/").text
    assert 'data-locked="2"' in c.get("/progress").text


def test_unlocking_opens_the_session_and_continue_moves_on(root):
    c = app(root)
    finish_session_1(c)
    assert c.get("/api/course/sessions/2").status_code == 200
    assert "<article" in c.get("/sessions/2").text
    assert c.get("/api/course").json()["continue"] == {"session": 2, "step_id": "a1"}


def test_undoing_a_step_locks_the_next_session_again_but_keeps_its_progress(root):
    c = app(root)
    finish_session_1(c)
    c.post("/api/course/sessions/2/steps/a1/complete", json={"done": True})
    c.post("/api/course/sessions/1/steps/v1/complete", json={"done": False})
    assert status(c, 2) == "locked"
    c.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    assert c.get("/api/course").json()["sessions"][1]["done"] == 1


def test_unlock_all_switch_opens_everything(root):
    c = app(root, unlock_all=True)
    assert status(c, 2) == "not-started" and c.get("/api/course/sessions/2").status_code == 200
