"""The course app and the service desk share no code and no routes."""
import re
from pathlib import Path

from fastapi.testclient import TestClient


def imports_of(package):
    found = set()
    for path in Path(package).rglob("*.py"):
        found |= set(re.findall(r"^\s*(?:from|import)\s+([a-zA-Z_]+)", path.read_text(), re.M))
    return found


def test_neither_app_imports_the_other():
    assert "servicedesk" not in imports_of("course")
    assert "course" not in imports_of("servicedesk")


def test_service_desk_serves_no_course_pages(db_path):
    from servicedesk.app import create_app
    c = TestClient(create_app(db_path=db_path))
    for url in ["/sessions/1", "/results", "/api/course"]:
        assert c.get(url).status_code == 404, url


def test_each_app_has_its_own_stylesheet(db_path, lab_root):
    from course.app import create_app as course_app
    from servicedesk.app import create_app as desk_app
    course = TestClient(course_app(data_dir=str(lab_root / "data"), lessons_dir=str(lab_root / "lessons")))
    desk = TestClient(desk_app(db_path=db_path))
    assert course.get("/static/app.css").status_code == 200 and desk.get("/static/desk.css").status_code == 200
    assert desk.get("/static/app.css").status_code == 404 and course.get("/static/desk.css").status_code == 404
    assert "Service Desk" in desk.get("/incidents").text and "Service Desk" not in course.get("/sessions/1").text
