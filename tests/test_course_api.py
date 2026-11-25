import pytest
from fastapi.testclient import TestClient

import course.checks
from course.app import create_app

S = "/api/course/sessions/1"


@pytest.fixture
def client(lab_root):
    app = create_app(data_dir=str(lab_root / "data"), lessons_dir=str(lab_root / "lessons"))
    return TestClient(app)


def step(client, step_id):
    steps = client.get(S).json()["steps"]
    return next(s for s in steps if s["id"] == step_id)


def lesson(lab_root):
    return lab_root / "lessons" / "01-tokenization"


def test_overview_lists_all_sessions(client):
    r = client.get("/api/course").json()
    assert len(r["sessions"]) == 14
    assert r["sessions"][0]["status"] == "not-started" and r["sessions"][0]["total"] == 7
    assert r["sessions"][1]["status"] == "not-released"
    assert r["overall"] == {"done": 0, "total": 7}
    assert r["continue"] == {"session": 1, "step_id": "v1"}


def test_manual_complete_and_unmark(client):
    assert client.post(f"{S}/steps/v1/complete", json={"done": True}).status_code == 200
    assert step(client, "v1")["done"] is True
    client.post(f"{S}/steps/v1/complete", json={"done": False})
    assert step(client, "v1")["done"] is False


def test_auto_source_is_recorded(client, lab_root):
    client.post(f"{S}/steps/v1/complete", json={"done": True, "source": "auto"})
    assert '"source": "auto"' in (lab_root / "data" / "progress.json").read_text()


def test_exercise_cannot_be_ticked(client):
    r = client.post(f"{S}/steps/ex1/complete", json={"done": True})
    assert r.status_code == 409 and "tests pass" in r.json()["detail"]
    assert step(client, "ex1")["done"] is False


def test_check_pass_marks_done(client):
    assert client.post(f"{S}/steps/ex1/check").json()["passed"] is True
    assert step(client, "ex1")["done"] is True


def test_check_fail_unmarks_and_returns_output(client, lab_root):
    client.post(f"{S}/steps/ex1/check")
    (lesson(lab_root) / "test_ex.py").write_text("def test_it():\n    assert 1 == 2\n")
    r = client.post(f"{S}/steps/ex1/check").json()
    assert r["passed"] is False and "assert" in r["output"]
    assert step(client, "ex1")["done"] is False


def test_check_survives_syntax_error_in_learner_code(client, lab_root):
    (lesson(lab_root) / "ex.py").write_text("def f(:\n")
    (lesson(lab_root) / "test_ex.py").write_text("from ex import f\n\ndef test_it():\n    assert f() == 2\n")
    r = client.post(f"{S}/steps/ex1/check").json()
    assert r["passed"] is False and "SyntaxError" in r["output"]
    assert client.get("/api/course").status_code == 200


def test_check_times_out(client, lab_root, monkeypatch):
    monkeypatch.setattr(course.checks, "DEFAULT_TIMEOUT", 2)
    (lesson(lab_root) / "test_ex.py").write_text("def test_it():\n    while True:\n        pass\n")
    r = client.post(f"{S}/steps/ex1/check").json()
    assert r["passed"] is False and "Timed out" in r["output"]


def test_check_only_for_exercises(client):
    assert client.post(f"{S}/steps/v1/check").status_code == 409


def test_answer_saved_and_bounded(client):
    assert client.post(f"{S}/steps/exp1/answer", json={"text": "I predict 12"}).status_code == 200
    assert step(client, "exp1")["answer"] == "I predict 12"
    assert client.post(f"{S}/steps/exp1/answer", json={"text": "x" * 20001}).status_code == 422
    assert client.post(f"{S}/steps/v1/answer", json={"text": "no"}).status_code == 409


def test_unknown_things_are_404_with_detail(client):
    for method, url in [("get", "/api/course/sessions/99"), ("get", "/api/course/sessions/2"),
                        ("post", f"{S}/steps/nope/complete"), ("post", f"{S}/steps/nope/check")]:
        r = getattr(client, method)(url, **({"json": {"done": True}} if "complete" in url else {}))
        assert r.status_code == 404 and "detail" in r.json(), url


def test_results_empty_by_default(client):
    assert client.get("/api/course/results").json() == {"runs": []}


def test_corrupt_progress_file_does_not_break_the_app(client, lab_root):
    (lab_root / "data" / "progress.json").write_text("{oops")
    assert client.get("/api/course").json()["overall"]["done"] == 0


def test_check_output_has_no_terminal_colour_codes(client, lab_root, monkeypatch):
    monkeypatch.setenv("FORCE_COLOR", "1")
    (lesson(lab_root) / "test_ex.py").write_text("def test_it():\n    assert 1 == 2\n")
    assert "\x1b" not in client.post(f"{S}/steps/ex1/check").json()["output"]


def test_missing_pytorch_gets_a_plain_instruction(client, lab_root):
    (lesson(lab_root) / "test_ex.py").write_text(
        "def test_it():\n    raise ModuleNotFoundError(\"No module named 'torch'\")\n")
    out = client.post(f"{S}/steps/ex1/check").json()["output"]
    assert out.startswith("This exercise needs PyTorch") and "make setup-lessons" in out


def test_runs_endpoint_lists_saved_runs_and_skips_broken_files(client, lab_root):
    assert client.get("/api/course/runs").json() == {"runs": []}
    runs = lab_root / "data" / "runs"
    runs.mkdir()
    (runs / "a.json").write_text('{"name": "a", "saved_at": "2026-01-01T00:00:00Z", "train_loss": [1]}')
    (runs / "b.json").write_text('{"name": "b", "saved_at": "2026-02-01T00:00:00Z", "train_loss": [2]}')
    (runs / "broken.json").write_text("{nope")
    assert [r["name"] for r in client.get("/api/course/runs").json()["runs"]] == ["b", "a"]


def test_data_folder_can_be_set_from_the_environment(lab_root, monkeypatch):
    other = lab_root / "elsewhere"
    monkeypatch.setenv("COURSE_DATA_DIR", str(other))
    c = TestClient(create_app(lessons_dir=str(lab_root / "lessons")))
    c.post(f"{S}/steps/v1/complete", json={"done": True})
    assert (other / "progress.json").exists() and not (lab_root / "data" / "progress.json").exists()
