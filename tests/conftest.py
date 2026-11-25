import textwrap
from pathlib import Path

import pytest
import yaml

TITLES = [
    ("tokenization", "Fundamentals", "Tokenization"),
    ("next-token", "Fundamentals", "Predicting the next token"),
    ("attention", "Fundamentals", "Attention"),
    ("tiny-gpt", "Fundamentals", "A tiny GPT"),
    ("toy-to-real", "Fundamentals", "From toy to real"),
    ("baseline", "The agent", "Baseline and measurement"),
    ("embeddings", "The agent", "Embeddings for search"),
    ("rag", "The agent", "RAG"),
    ("tool-calling", "The agent", "Tool calling"),
    ("agent", "The agent", "The agent"),
    ("guardrails", "The agent", "Guardrails and failure"),
    ("framework", "The agent", "Framework port"),
    ("fine-tuning", "The agent", "Fine-tuning versus RAG"),
    ("capstone", "The agent", "Capstone"),
]

STEPS = [
    {"id": "v1", "kind": "video", "title": "Watch <script>alert(1)</script>", "section": "Pre-work",
     "youtube_id": "abc123XYZ_-", "start": 0, "end": 600, "channel": "Some Channel",
     "watch_for": ["one", "two", "three"]},
    {"id": "r1", "kind": "reading", "title": "Read the paper", "section": "Pre-work",
     "url": "https://example.org/paper", "source": "arXiv", "note": "Sections 1 and 3"},
    {"id": "c1", "kind": "concept", "title": "The idea", "section": "Session", "file": "concept/a.html"},
    {"id": "ex1", "kind": "exercise", "title": "Fill the gap", "section": "Session", "file": "ex.py",
     "test": "lessons/01-tokenization/test_ex.py::test_it", "brief": "Make it return 2"},
    {"id": "exp1", "kind": "experiment", "title": "Try it", "section": "Session",
     "prompt": "What do you predict?", "command": "python ex.py"},
    {"id": "p1", "kind": "problem", "title": "Problem 1", "section": "Homework",
     "prompt": "Trace two merges", "answer": "ab then abc", "points": 5},
    {"id": "q1", "kind": "review", "title": "Question 1", "section": "Homework",
     "question": "Why sub-word?", "model_answer": "Balance of vocabulary size and coverage"},
]


def write_lessons(root: Path, steps=STEPS) -> Path:
    lessons = root / "lessons"
    lessons.mkdir(exist_ok=True)
    course = [{"number": i + 1, "slug": s, "phase": p, "title": t, "summary": f"About {t.lower()}"}
              for i, (s, p, t) in enumerate(TITLES)]
    (lessons / "course.yaml").write_text(yaml.safe_dump(course))
    s1 = lessons / "01-tokenization"
    (s1 / "concept").mkdir(parents=True, exist_ok=True)
    (s1 / "widgets").mkdir(exist_ok=True)
    (s1 / "_solution").mkdir(exist_ok=True)
    (s1 / "concept" / "a.html").write_text("<p>Text becomes numbers.</p>")
    (s1 / "widgets" / "w.js").write_text("// widget")
    (s1 / "_solution" / "ex.py").write_text("def f():\n    return 2\n")
    (s1 / "ex.py").write_text("def f():\n    return 2\n")
    (s1 / "test_ex.py").write_text(textwrap.dedent("""
        def test_it():
            assert True
    """))
    (s1 / "session.yaml").write_text(yaml.safe_dump({"steps": steps}))
    return lessons


@pytest.fixture
def lab_root(tmp_path):
    write_lessons(tmp_path)
    (tmp_path / "data").mkdir()
    return tmp_path


@pytest.fixture
def tmp_lessons(lab_root):
    return str(lab_root / "lessons")


@pytest.fixture(scope="session")
def generated():
    from servicedesk.generate import build_deploys, build_incidents
    return build_incidents(), build_deploys()


@pytest.fixture
def db_path(tmp_path, generated):
    from servicedesk import db
    path = str(tmp_path / "timetravel.db")
    conn = db.connect(path)
    db.load(conn, *generated)
    conn.close()
    return path
