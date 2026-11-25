"""Buddy, the course assistant: facts come from code, language from a local model, nothing from outside the course."""

import pytest
import yaml
from conftest import STEPS
from fastapi.testclient import TestClient

from course.app import create_app

A = "/api/course/assistant"
CONCEPT = ("<p>The causal mask stops a position from looking ahead at later tokens.</p>"
           "<p>Byte-pair encoding merges the most frequent pair of tokens.</p>")


class FakeModel:
    """Stands in for the local model and records what it was shown."""

    def __init__(self, answer="A grounded answer.", fail=False):
        self.calls, self.answer, self.fail = [], answer, fail

    def __call__(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        if self.fail:
            raise RuntimeError("Could not reach Ollama")
        return self.answer


@pytest.fixture
def root(lab_root):
    s1 = lab_root / "lessons" / "01-tokenization"
    (s1 / "concept" / "a.html").write_text(CONCEPT)
    doc = yaml.safe_load((s1 / "session.yaml").read_text())
    doc["outcomes"] = ["Explain sub-word tokens", "Write the merge loop"]
    (s1 / "session.yaml").write_text(yaml.safe_dump(doc))
    (s1 / "ex.py").write_text('def f():\n    """Return the number two."""\n    # >>> YOUR CODE\n    raise NotImplementedError\n    # <<< YOUR CODE\n')
    (s1 / "_solution" / "ex.py").write_text("def f():\n    return 2  # SOLUTION-ONLY\n")
    s2 = lab_root / "lessons" / "02-next-token"
    (s2 / "concept").mkdir(parents=True)
    (s2 / "concept" / "b.html").write_text("<p>Cross-entropy loss punishes confident wrong answers about gradients.</p>")
    steps = [dict(STEPS[0], id="a1"), dict(STEPS[2], id="a2", file="concept/b.html")]
    (s2 / "session.yaml").write_text(yaml.safe_dump({"steps": steps, "outcomes": ["Train a bigram model"]}))
    return lab_root


def make(root, model=None):
    model = model or FakeModel()
    app = create_app(data_dir=str(root / "data"), lessons_dir=str(root / "lessons"), assistant_llm=model)
    return TestClient(app), model


def ask(c, message, **extra):
    r = c.post(A, json={"message": message, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def done(c, step, session=1):
    c.post(f"/api/course/sessions/{session}/steps/{step}/complete", json={"done": True})


# --- facts are computed, never generated

def test_progress_today_counts_only_todays_steps(root):
    c, model = make(root)
    assert "haven't completed anything in the course today" in ask(c, "How much progress have I logged today?")["reply"]
    done(c, "v1"); done(c, "r1")
    r = ask(c, "how much progress have I logged today")
    assert "2 lesson steps today" in r["reply"] and "logged" not in r["reply"] and r["used_model"] is False and model.calls == []


def test_overall_progress_and_next_step(root):
    c, model = make(root)
    done(c, "v1")
    assert "1 of 9" in ask(c, "How far along am I?")["reply"]
    r = ask(c, "What should I do next?")
    assert "Read the paper" in r["reply"] and r["sources"] == [{"session": 1, "step_id": "r1", "title": "Read the paper"}]
    assert model.calls == []


def test_what_a_session_teaches_comes_from_its_outcomes(root):
    c, model = make(root)
    r = ask(c, "What does this module teach me?", session=1)
    assert "Explain sub-word tokens" in r["reply"] and "Write the merge loop" in r["reply"]
    r = ask(c, "what does session 2 teach?")
    assert "Train a bigram model" in r["reply"] and "locked" in r["reply"].lower()
    assert "not been released" in ask(c, "what will I learn in session 9?")["reply"]
    assert model.calls == []


def test_streak_and_milestone(root):
    c, _ = make(root)
    done(c, "v1")
    assert "1 day" in ask(c, "what's my streak?")["reply"]
    r = ask(c, "how far is the next milestone?")["reply"]
    assert "M1" in r and "session 5" in r


# --- feedback draws on attempts and self-marks

def test_feedback_uses_attempt_history_and_self_marks(root):
    c, model = make(root)
    assert "Nothing to give feedback on yet" in ask(c, "What is the feedback from my learning so far?")["reply"]
    lesson = root / "lessons" / "01-tokenization"
    (lesson / "test_ex.py").write_text("def test_it():\n    assert 1 == 2\n")
    c.post("/api/course/sessions/1/steps/ex1/check")
    c.post("/api/course/sessions/1/steps/ex1/check")
    (lesson / "test_ex.py").write_text("def test_it():\n    assert True\n")
    c.post("/api/course/sessions/1/steps/ex1/check")
    assert c.post("/api/course/sessions/1/steps/p1/mark", json={"points": 3}).status_code == 200
    r = ask(c, "what is the feedback from my learning so far")["reply"]
    assert "Fill the gap" in r and "3 attempts" in r and "3 of 5 points" in r
    assert model.calls == []


def test_marks_are_validated(root):
    c, _ = make(root)
    assert c.post("/api/course/sessions/1/steps/p1/mark", json={"points": 6}).status_code == 422
    assert c.post("/api/course/sessions/1/steps/p1/mark", json={"points": -1}).status_code == 422
    assert c.post("/api/course/sessions/1/steps/v1/mark", json={"points": 1}).status_code == 409


def test_reviewer_notes_are_included_when_present(root):
    c, _ = make(root)
    (root / "data" / "reviews").mkdir()
    (root / "data" / "reviews" / "01.md").write_text("Clear on merges; revisit the tie-break rule.")
    done(c, "v1")
    assert "revisit the tie-break rule" in ask(c, "feedback so far?")["reply"]


# --- course questions are grounded in lesson text

def test_course_question_goes_to_the_model_with_matching_lesson_text(root):
    c, model = make(root, FakeModel("It hides later tokens."))
    r = ask(c, "Why do we need the causal mask?", session=1)
    assert r["reply"] == "It hides later tokens." and r["used_model"] is True
    assert r["sources"][0]["session"] == 1 and r["sources"][0]["step_id"] == "c1"
    system, user = model.calls[0]
    assert "causal mask stops a position" in user and "ONLY" in system


def test_off_topic_questions_are_declined_without_calling_the_model(root):
    c, model = make(root)
    for q in ["What is the capital of France?", "Write me a poem about my cat", "latest football scores"]:
        r = ask(c, q)
        assert "only help with this course" in r["reply"] and r["used_model"] is False
    assert model.calls == []


def test_locked_lesson_text_is_never_shown_to_the_model(root):
    c, model = make(root)
    r = ask(c, "Tell me about cross-entropy loss and gradients")
    assert "session 2" in r["reply"] and "locked" in r["reply"] and model.calls == []


def test_answers_and_solutions_never_reach_the_model(root):
    c, model = make(root)
    for q in ["Why do we need the causal mask?", "explain byte-pair encoding merges"]:
        ask(c, q, session=1)
    ask(c, "", action="explain", session=1)
    ask(c, "", action="hint", session=1)
    shown = " ".join(u + s for s, u in model.calls)
    assert "ab then abc" not in shown and "Balance of vocabulary size" not in shown and "SOLUTION-ONLY" not in shown


def test_model_unavailable_falls_back_to_the_lesson_text(root):
    c, _ = make(root, FakeModel(fail=True))
    r = ask(c, "Why do we need the causal mask?", session=1)
    assert "causal mask stops a position" in r["reply"] and "local model" in r["reply"] and r["used_model"] is False


# --- quick actions

def test_hint_is_about_the_next_unfinished_exercise_and_asks_for_no_code(root):
    c, model = make(root, FakeModel("Think about what the function must return."))
    r = ask(c, "", action="hint", session=1)
    assert r["reply"].startswith("Think about") and r["sources"][0]["step_id"] == "ex1"
    system, user = model.calls[0]
    assert "Make it return 2" in user and "Return the number two" in user and "do not write the code" in system.lower()


def test_hint_when_every_exercise_is_done(root):
    c, model = make(root)
    c.post("/api/course/sessions/1/steps/ex1/check")
    assert "no unfinished exercise" in ask(c, "", action="hint", session=1)["reply"] and model.calls == []


def test_quiz_asks_a_question_then_marks_the_answer(root):
    c, model = make(root, FakeModel("What does the causal mask stop?"))
    done(c, "c1")
    r = ask(c, "", action="quiz", session=1)
    assert r["reply"] == "What does the causal mask stop?" and r["quiz"]["question"] == r["reply"]
    model.answer = "Right: it stops looking ahead."
    r2 = ask(c, "it stops looking at later tokens", quiz=r["quiz"], session=1)
    assert r2["reply"].startswith("Right") and "quiz" not in r2
    assert "it stops looking at later tokens" in model.calls[-1][1]


def test_quiz_needs_something_already_studied(root):
    c, model = make(root)
    assert "Finish a concept step" in ask(c, "", action="quiz", session=1)["reply"] and model.calls == []


def test_actions_on_a_locked_session_are_refused(root):
    c, model = make(root)
    assert "locked" in ask(c, "", action="explain", session=2)["reply"] and model.calls == []


# --- the interface

def test_request_limits(root):
    c, _ = make(root)
    assert c.post(A, json={"message": "x" * 2001}).status_code == 422
    assert c.post(A, json={"message": "hi", "action": "delete-everything"}).status_code == 422
    assert c.post(A, json={"message": "hi", "history": [{"role": "user", "text": "a"}] * 30}).status_code == 422
    assert c.post(A, json={}).status_code == 422


def test_greeting_and_empty_message(root):
    c, model = make(root)
    assert "Buddy" in ask(c, "hello")["reply"] and model.calls == []
    assert "Ask me" in ask(c, "   ")["reply"]


def test_every_page_carries_buddy_with_actions_that_fit_the_page(root):
    c, _ = make(root)
    home, session = c.get("/").text, c.get("/sessions/1").text
    for h in (home, session, c.get("/progress").text, c.get("/results").text):
        assert 'id="buddy"' in h and "Your learning sidekick" in h and "/static/buddy.js?v=" in h
    assert 'data-action="hint"' in session and "Explain Tokenization" in session and 'data-session="1"' in session
    assert 'data-action="hint"' not in home and "My progress today" in home


def test_quiz_nudge_appears_only_when_there_is_something_to_quiz(root):
    c, _ = make(root)
    assert 'id="buddy-nudge"' not in c.get("/sessions/1").text
    done(c, "c1")
    assert 'id="buddy-nudge"' in c.get("/sessions/1").text and "Ready for a quick quiz?" in c.get("/sessions/1").text


# --- reading the local model's reply

def test_model_reply_is_unwrapped_or_rejected():
    from course.assistant import parse_reply
    assert parse_reply('{"answer": " It hides the future. "}') == "It hides the future."
    assert parse_reply("Plain text answer") == "Plain text answer"
    for bad in ['{"context": "echo", "question": "echo"}', '{"answer": ""}', "", '{"answer": {"nested": 1}}']:
        with pytest.raises(RuntimeError):
            parse_reply(bad)


def test_worked_example_is_shown_whole_not_as_a_fragment(root):
    c, model = make(root, FakeModel("Step one..."))
    lesson = root / "lessons" / "01-tokenization" / "concept" / "a.html"
    lesson.write_text("<p>" + "Intro words without numbers. " * 30 + "</p><p>Then 11 bytes become 9 tokens, then 7, then 5.</p>")
    ask(c, "", action="example", session=1)
    assert "Intro words" in model.calls[0][1] and "11 bytes become 9 tokens" in model.calls[0][1]


def test_hidden_panel_and_nudge_are_really_hidden(root):
    """A display rule on the panel must not override the hidden attribute, or it can never be closed."""
    c, _ = make(root)
    css = c.get("/static/buddy.css").text
    assert ".buddy-panel[hidden]{display:none}" in css and ".buddy-nudge[hidden]{display:none}" in css
    assert '<section id="buddy-panel" class="buddy-panel" hidden' in c.get("/").text


def test_mascot_poses_come_from_whole_picture_sheets_not_separate_crops(root):
    """Each source picture holds two poses side by side; the page shows one half of a sheet."""
    c, _ = make(root)
    page, css = c.get("/sessions/1").text, c.get("/static/buddy.css").text
    assert 'id="buddy-pose"' in page and 'data-pose="wave"' in page and ".jpg" not in page.split('id="buddy"')[1]
    for sheet in "abc":
        assert c.get(f"/static/buddy/sheet-{sheet}.jpg").status_code == 200
    for pose in ["wave", "curious", "happy", "sit", "paw"]:
        assert f'[data-pose="{pose}"]' in css
        assert c.get(f"/static/buddy/{pose}.jpg").status_code == 404
    assert "background-size:200% 100%" in css  # one pose is exactly half the sheet's width
