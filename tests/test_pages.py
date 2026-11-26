import re
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from course.app import create_app


@pytest.fixture
def client(lab_root):
    return TestClient(create_app(data_dir=str(lab_root / "data"), lessons_dir=str(lab_root / "lessons")))


def block(html, step_id):
    m = re.search(rf'<article[^>]*id="step-{step_id}".*?</article>', html, re.S)
    assert m, f"no step block for {step_id}"
    return m.group(0)


def test_home_lists_sessions_and_progress(client):
    h = client.get("/").text
    assert "Tokenization" in h and h.count("<li data-session=") == 14
    assert "Not yet released" in h and "0 of 7" in h


def test_home_continue_link_points_to_first_open_step(client):
    assert 'href="/sessions/1#step-v1"' in client.get("/").text
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    assert 'href="/sessions/1#step-r1"' in client.get("/").text


def test_session_page_renders_every_kind(client):
    h = client.get("/sessions/1").text
    for k in ["video", "reading", "concept", "exercise", "experiment", "problem", "review"]:
        assert f'data-kind="{k}"' in h
    assert "Text becomes numbers." in h  # concept fragment is inlined


def test_video_step_has_fallback_link_and_manual_control(client):
    b = block(client.get("/sessions/1").text, "v1")
    assert 'href="https://www.youtube.com/watch?v=abc123XYZ_-&amp;t=0s"' in b
    assert 'data-action="complete"' in b and 'data-youtube="abc123XYZ_-"' in b
    assert "youtube.com/embed" not in b and "ytimg" not in b  # nothing loads until clicked


def test_exercise_has_check_button_not_tick(client):
    b = block(client.get("/sessions/1").text, "ex1")
    assert 'data-action="check"' in b and 'data-action="complete"' not in b


def test_done_state_is_rendered(client):
    client.post("/api/course/sessions/1/steps/r1/complete", json={"done": True})
    assert 'data-done="true"' in block(client.get("/sessions/1").text, "r1")
    assert 'data-done="false"' in block(client.get("/sessions/1").text, "v1")


def test_saved_answer_is_rendered(client):
    client.post("/api/course/sessions/1/steps/exp1/answer", json={"text": "I predict <12>"})
    assert "I predict &lt;12&gt;" in block(client.get("/sessions/1").text, "exp1")


def test_unreleased_session_page(client):
    r = client.get("/sessions/2")
    assert r.status_code == 200 and "Not yet released" in r.text and "Predicting the next token" in r.text


def test_unknown_session_page_404(client):
    assert client.get("/sessions/99").status_code == 404


def test_lesson_text_is_escaped(client):
    h = client.get("/sessions/1").text
    assert "&lt;script&gt;alert(1)" in h and "<script>alert(1)" not in h


def test_lessons_static_only_serves_concept_and_widgets(client):
    assert client.get("/lessons-static/01-tokenization/widgets/w.js").status_code == 200
    assert client.get("/lessons-static/01-tokenization/_solution/ex.py").status_code == 404
    assert client.get("/lessons-static/01-tokenization/ex.py").status_code == 404
    assert client.get("/lessons-static/01-tokenization/widgets/%2e%2e/ex.py").status_code == 404


def test_session_notice_is_shown(client, lab_root):
    path = lab_root / "lessons" / "01-tokenization" / "session.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["notice"] = "More steps arrive soon."
    path.write_text(yaml.safe_dump(doc))
    assert "More steps arrive soon." in client.get("/sessions/1").text


def test_results_page_empty_state(client):
    r = client.get("/results")
    assert r.status_code == 200 and "No runs yet" in r.text


def test_results_page_shows_fractions_as_percentages_and_gaps_as_dashes(client, lab_root):
    import json
    runs = [{"name": "Keep the reporter's priority", "priority_exact": 0.85, "priority_within_one": 1.0,
             "service": None, "hit_at_5": None, "seconds": 0},
            {"name": "Model alone", "priority_exact": 0.305, "priority_within_one": 0.9, "service": 0.62, "seconds": 1.4}]
    (lab_root / "data" / "results.json").write_text(json.dumps({"runs": runs}))
    h = client.get("/results").text
    assert "No runs yet" not in h and "Keep the reporter&#39;s priority" in h
    for shown in ["85%", "100%", "30%", "90%", "62%", "1.4"]:
        assert f"<td>{shown}</td>" in h, shown
    assert h.count("<td>–</td>") == 4  # first row: service, related-in-top-5 and time; second row: related-in-top-5


def test_real_session_1_page_renders():
    c = TestClient(create_app(data_dir="/nonexistent-data-dir-for-test", lessons_dir="lessons"))
    h = c.get("/sessions/1").text
    assert "zduSFxRajkE" in h and "LPZh9BOjkQs" in h and "1508.07909" in h


def test_problem_shows_worked_answer_separately_from_learner_answer(client):
    client.post("/api/course/sessions/1/steps/p1/answer", json={"text": "my attempt"})
    b = block(client.get("/sessions/1").text, "p1")
    assert "ab then abc" in b and "my attempt" in b
    p1 = next(s for s in client.get("/api/course/sessions/1").json()["steps"] if s["id"] == "p1")
    assert p1["answer_key"] == "ab then abc" and p1["answer"] == "my attempt"


# --- the course app and the service desk are separate applications

def test_course_links_out_to_the_service_desk(lab_root):
    c = TestClient(create_app(data_dir=str(lab_root / "data"), lessons_dir=str(lab_root / "lessons"),
                              desk_url="http://desk.test:9999"))
    h = c.get("/").text
    assert 'href="http://desk.test:9999"' in h and 'target="_blank"' in h


def test_course_app_serves_no_ticket_pages_or_ticket_api(client):
    for url in ["/incidents", "/incidents/INC0010001", "/api/now/table/incident", "/api/services", "/api/eval/incidents"]:
        assert client.get(url).status_code == 404, url


# --- the learning-platform layout

def test_nav_has_sessions_progress_results_and_desk(client):
    h = client.get("/").text
    for href in ['href="/"', 'href="/progress"', 'href="/results"']:
        assert href in h


def test_home_has_a_hero_with_one_call_to_action(client):
    h = client.get("/").text
    assert 'class="hero"' in h and "Start session 1" in h
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    assert "Continue session 1" in client.get("/").text


def test_progress_page_shows_completion_streak_and_what_to_continue(client):
    h = client.get("/progress").text
    assert 'data-overall="0"' in h and "0 of 7 steps" in h and "0 days" in h
    assert "Nothing in progress yet" in h
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    h = client.get("/progress").text
    assert 'data-overall="14"' in h and "1 of 7 steps" in h and "1 day" in h and "1 days" not in h
    assert 'href="/sessions/1#step-r1"' in h and "Tokenization" in h and "Nothing in progress yet" not in h


def test_progress_page_lists_completed_sessions(client):
    for sid in ["v1", "r1", "c1", "exp1", "p1", "q1"]:
        client.post(f"/api/course/sessions/1/steps/{sid}/complete", json={"done": True})
    client.post("/api/course/sessions/1/steps/ex1/check")
    h = client.get("/progress").text
    assert 'data-overall="100"' in h and 'data-completed="1"' in h


def test_session_header_shows_what_it_includes_and_a_continue_button(client):
    h = client.get("/sessions/1").text
    assert "This session includes" in h and "1 video" in h and "1 coding exercise" in h and "10 min of video" in h
    assert 'href="#step-v1"' in h and "Start" in h


def test_session_outcomes_are_listed_when_given(client, lab_root):
    path = lab_root / "lessons" / "01-tokenization" / "session.yaml"
    doc = yaml.safe_load(path.read_text())
    doc["outcomes"] = ["Explain why models use sub-word tokens", "Write the merge loop"]
    path.write_text(yaml.safe_dump(doc))
    h = client.get("/sessions/1").text
    assert "What you'll learn" in h.replace("&#39;", "'") and "Write the merge loop" in h


def test_real_session_1_has_outcomes():
    c = TestClient(create_app(data_dir="/nonexistent-data-dir-for-test", lessons_dir="lessons"))
    assert c.get("/sessions/1").text.count('class="outcome"') >= 3


def test_progress_ring_draws_no_arc_at_zero(client):
    assert 'class="arc"' not in client.get("/progress").text
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    assert 'class="arc"' in client.get("/progress").text


# --- side-rail layout and the dashboard home page

def test_every_page_has_the_side_rail_and_no_search_bar(client):
    """Buddy is asked only from his own chat panel; there is no second way in at the top."""
    for url in ["/", "/sessions/1", "/progress", "/results"]:
        h = client.get(url).text
        assert 'class="sidebar"' in h and "buddy-ask-top" not in h and 'class="askbar"' not in h, url
        assert "steps done" in h.split('class="sidebar"')[1].split("</aside>")[0], url  # the counter lives in the rail
        assert h.count('aria-current="page"') == 1, url


def test_home_recommends_up_to_three_sessions_starting_with_the_current_one(client):
    h = client.get("/").text
    picks = re.findall(r'data-pick="(\d+)"', h)
    assert picks == ["1"]  # only one session is released in this fixture
    assert "Continue learning" in h and 'href="/sessions/1#step-v1"' in h


def test_home_progress_ring_and_session_counts_are_computed(client):
    h = client.get("/").text
    assert 'data-overall="0"' in h
    assert re.search(r'data-count="completed">0<', h) and re.search(r'data-count="in-progress">0<', h)
    assert re.search(r'data-count="not-started">1<', h) and re.search(r'data-count="not-built">13<', h)
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    h = client.get("/").text
    assert 'data-overall="14"' in h and re.search(r'data-count="in-progress">1<', h)


def test_home_tiles_show_streak_week_and_next_milestone(client):
    h = client.get("/").text
    assert 'data-tile="streak">0 days<' in h and 'data-tile="week">0<' in h and "M1" in h and "session 5" in h
    client.post("/api/course/sessions/1/steps/v1/complete", json={"done": True})
    h = client.get("/").text
    assert 'data-tile="streak">1 day<' in h and 'data-tile="week">1<' in h
    assert "32h" not in h and "Total learning time" not in h  # nothing the app cannot measure


def test_learning_paths_summarise_the_two_phases(client):
    h = client.get("/").text
    assert h.count('data-path=') == 2 and "5 sessions" in h and "9 sessions" in h


def test_static_files_carry_a_version_so_browsers_never_show_stale_styles(client):
    h = client.get("/").text
    for name in ["tokens.css", "app.css", "buddy.css", "app.js", "buddy.js"]:
        assert re.search(rf'/static/{re.escape(name)}\?v=\d+"', h), name
    assert client.get("/static/app.css?v=1").status_code == 200


# --- session and phase icons (outline with an accent bar)

def test_every_session_has_its_own_icon_on_the_home_page(client):
    h = client.get("/").text
    block = h.split('id="all-sessions"')[1]
    assert sorted(set(int(n) for n in re.findall(r'data-icon="(\d+)"', block))) == list(range(1, 15))
    paths = re.findall(r'data-icon="(\d+)"[^>]*>.*?<path d="([^"]+)"', block, re.S)
    assert len({d for _, d in paths}) == 14  # fourteen different drawings
    assert 'data-emblem="1"' in h and 'data-emblem="2"' in h


def test_icon_states_follow_the_session_status(lab_root):
    s2 = lab_root / "lessons" / "02-next-token"
    s2.mkdir()
    (s2 / "session.yaml").write_text(yaml.safe_dump({"steps": [dict(conftest_steps()[0], id="a1")]}))
    c = TestClient(create_app(data_dir=str(lab_root / "data"), lessons_dir=str(lab_root / "lessons")))
    block = c.get("/").text.split('id="all-sessions"')[1]
    icon = lambda n: re.search(rf'<span class="sicon[^"]*" data-icon="{n}".*?</span></span>(?:<span class="lock".*?</span>)?', block, re.S).group(0)
    assert "locked" not in icon(1) and "unbuilt" not in icon(1) and 'class="lock"' not in icon(1)
    assert 'class="sicon p1 locked' in icon(2) and 'class="lock"' in icon(2)       # blurred under a lock
    assert 'class="sicon p1 unbuilt' in icon(3) and 'class="lock"' not in icon(3)  # not built yet: greyed, no lock
    assert 'class="sicon p2' in icon(6)


def test_session_and_progress_pages_use_the_icons(client):
    assert 'data-icon="1"' in client.get("/sessions/1").text
    assert 'data-icon="1"' in client.get("/progress").text
    assert 'data-icon="2"' in client.get("/sessions/2").text  # an unreleased session still shows its icon


def test_icon_set_is_complete():
    from course.icons import PHASE_ICONS, SESSION_ICONS
    assert sorted(SESSION_ICONS) == list(range(1, 15)) and sorted(PHASE_ICONS) == [1, 2]
    assert all(d.startswith("M") and '"' not in d and "<" not in d for d in list(SESSION_ICONS.values()) + list(PHASE_ICONS.values()))


def conftest_steps():
    from conftest import STEPS
    return STEPS


# --- the Agent Quest logo

def test_portal_shows_the_real_logo_mark_and_tab_icon(client):
    h = client.get("/").text
    side = h.split('class="sidebar"')[1].split("</aside>")[0]
    assert '<img src="/static/brand/mark-dark.png' in side and "Agent" in side and "Quest" in side
    assert "Solve Real Problems" in side and "<rect" not in side.split("</a>")[0]  # the placeholder square is gone
    assert '<link rel="icon" type="image/png" href="/static/brand/mark.png' in h
    for name in ["mark-dark.png", "mark.png"]:
        r = client.get(f"/static/brand/{name}")
        assert r.status_code == 200 and r.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_readme_opens_with_the_logo_and_every_local_image_exists():
    from pathlib import Path
    text = Path("README.md").read_text()
    assert text.lstrip().startswith('<p align="center">') and "agent-quest-logo.png" in text.split("##")[0]
    assert 'media="(prefers-color-scheme: dark)"' in text and "agent-quest-logo-dark.png" in text
    local = [p for p in re.findall(r'(?:src|srcset)="([^"]+)"|\]\(([^)]+\.(?:svg|png|jpg))\)', text)]
    paths = [a or b for a, b in local if not (a or b).startswith("http")]
    assert len(paths) >= 5 and all(Path(p).is_file() for p in paths), [p for p in paths if not Path(p).is_file()]


def test_all_three_logo_concepts_are_kept_on_file():
    from pathlib import Path
    names = sorted(p.name for p in Path("assets/brand/concepts").glob("*.png"))
    assert names == ["concept-1-compass.png", "concept-2-buddy.png", "concept-3-monogram.png"]


def test_a_switched_off_button_shows_a_busy_cursor_only_while_it_is_working(client):
    css = client.get("/static/app.css").text
    assert ".btn[disabled]{opacity:.6;cursor:not-allowed}" in css and '.btn[aria-busy="true"]{cursor:progress}' in css
    assert 'setAttribute("aria-busy", "true")' in client.get("/static/app.js").text
    widget = (Path(__file__).parent.parent / "lessons/01-tokenization/widgets/bpe-stepper.js").read_text()
    assert "Finished: no pair repeats" in widget
