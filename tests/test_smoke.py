"""End to end: generate the data, start both apps, load every page."""
from fastapi.testclient import TestClient

from conftest import write_lessons
from course.app import create_app as course_app
from servicedesk import generate
from servicedesk.app import create_app as desk_app


def test_whole_lab_from_scratch(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    progress = data / "progress.json"
    progress.write_text('{"steps": {"1/v1": {"done": true, "source": "manual", "at": "x"}}, "answers": {}, "checks": {}}')
    before = progress.read_bytes()

    generate.main(str(data))
    first = (data / "timetravel.db").read_bytes()
    generate.main(str(data))

    assert progress.read_bytes() == before  # regenerating data never touches progress
    assert (data / "corpus.txt").stat().st_size > 100_000
    assert (data / "timetravel.db").read_bytes() == first

    write_lessons(tmp_path)
    course = TestClient(course_app(data_dir=str(data), lessons_dir=str(tmp_path / "lessons")))
    for url in ["/", "/sessions/1", "/results", "/api/course", "/static/app.css"]:
        assert course.get(url).status_code == 200, url
    assert "1 of 7" in course.get("/").text

    desk = TestClient(desk_app(db_path=str(data / "timetravel.db")))
    for url in ["/incidents?view=open", "/incidents?view=resolved", "/incidents/INC0010001", "/incidents/new", "/services",
                "/api/now/table/incident", "/api/eval/incidents", "/static/desk.css"]:
        assert desk.get(url).status_code == 200, url


def test_generate_if_missing_leaves_existing_data_alone(tmp_path):
    data = tmp_path / "data"
    generate.main(str(data))
    marker = (data / "timetravel.db").stat().st_mtime_ns
    generate.main(str(data), if_missing=True)
    assert (data / "timetravel.db").stat().st_mtime_ns == marker


def test_real_lessons_render_with_real_static_files():
    client = TestClient(course_app(data_dir="/nonexistent-data-dir-for-test", lessons_dir="lessons"))
    page = client.get("/sessions/1").text
    assert "bpe-stepper" in page and page.count('data-kind="exercise"') == 4
    assert client.get("/lessons-static/01-tokenization/widgets/bpe-stepper.js").status_code == 200
