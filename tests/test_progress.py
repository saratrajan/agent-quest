from course.manifest import load_course
from course.progress import ProgressStore, summarise

EMPTY = {"steps": {}, "answers": {}, "checks": {}, "attempts": {}, "marks": {}}


def test_missing_file_is_empty(tmp_path):
    assert ProgressStore(tmp_path / "p.json").get() == EMPTY


def test_corrupt_file_is_set_aside_not_overwritten(tmp_path):
    p = tmp_path / "p.json"
    p.write_text("{not json")
    assert ProgressStore(p).get() == EMPTY
    kept = list(tmp_path.glob("p.json.corrupt-*"))
    assert len(kept) == 1 and kept[0].read_text() == "{not json"


def test_wrong_shape_is_treated_as_corrupt(tmp_path):
    p = tmp_path / "p.json"
    p.write_text("[1, 2, 3]")
    assert ProgressStore(p).get() == EMPTY
    assert len(list(tmp_path.glob("p.json.corrupt-*"))) == 1


def test_done_round_trips_and_can_be_unmarked(tmp_path):
    s = ProgressStore(tmp_path / "p.json")
    s.set_done(1, "v1", True, "manual")
    again = ProgressStore(tmp_path / "p.json").get()["steps"]["1/v1"]
    assert again["done"] is True and again["source"] == "manual" and again["at"]
    s.set_done(1, "v1", False, "manual")
    assert s.get()["steps"]["1/v1"]["done"] is False


def test_answer_and_check_are_kept(tmp_path):
    s = ProgressStore(tmp_path / "p.json")
    s.set_answer(1, "exp1", "I predict 12")
    s.set_check(1, "ex1", False, "boom")
    state = ProgressStore(tmp_path / "p.json").get()
    assert state["answers"]["1/exp1"] == "I predict 12"
    assert state["checks"]["1/ex1"]["passed"] is False and state["checks"]["1/ex1"]["output"] == "boom"


def test_summarise_counts_and_continue(tmp_lessons, tmp_path):
    sessions = load_course(tmp_lessons)
    store = ProgressStore(tmp_path / "p.json")
    out = summarise(sessions, store.get())
    assert out["sessions"][1] == {"done": 0, "total": 7, "status": "not-started"}
    assert out["sessions"][2]["status"] == "not-released"
    assert out["overall"] == {"done": 0, "total": 7}
    assert out["continue"] == {"session": 1, "step_id": "v1"}
    store.set_done(1, "v1", True, "manual")
    out = summarise(sessions, store.get())
    assert out["sessions"][1] == {"done": 1, "total": 7, "status": "in-progress"}
    assert out["continue"] == {"session": 1, "step_id": "r1"}


def test_summarise_all_done_has_no_continue(tmp_lessons, tmp_path):
    sessions = load_course(tmp_lessons)
    store = ProgressStore(tmp_path / "p.json")
    for st in sessions[0].steps:
        store.set_done(1, st["id"], True, "manual")
    out = summarise(sessions, store.get())
    assert out["sessions"][1]["status"] == "done" and out["continue"] is None


# --- learning streak

from datetime import UTC, date, datetime

from course.progress import streak


def state_with(*days):
    # stamped at local noon, converted to UTC the way the app stores it
    stamp = lambda d: datetime.fromisoformat(f"{d}T12:00:00").astimezone().astimezone(UTC).isoformat()
    return {"steps": {f"1/s{k}": {"done": True, "source": "manual", "at": stamp(d)} for k, d in enumerate(days)},
            "answers": {}, "checks": {}}


def test_streak_counts_consecutive_days_ending_today():
    assert streak(state_with("2026-11-22", "2026-11-23", "2026-11-24"), date(2026, 11, 24)) == 3


def test_streak_survives_until_the_end_of_the_next_day():
    assert streak(state_with("2026-11-22", "2026-11-23"), date(2026, 11, 24)) == 2


def test_streak_resets_after_a_missed_day():
    assert streak(state_with("2026-11-20", "2026-11-21"), date(2026, 11, 24)) == 0
    assert streak(state_with("2026-11-20", "2026-11-23", "2026-11-24"), date(2026, 11, 24)) == 2


def test_streak_ignores_unmarked_steps_and_empty_progress():
    s = state_with("2026-11-24")
    s["steps"]["1/s0"]["done"] = False
    assert streak(s, date(2026, 11, 24)) == 0 and streak({"steps": {}, "answers": {}, "checks": {}}, date(2026, 11, 24)) == 0


def test_streak_counts_a_step_done_late_in_the_evening_as_today():
    """Stored times are UTC. Late evening in the Americas is already tomorrow in UTC, and must still count as today."""
    local_late = datetime.combine(date(2026, 11, 24), datetime.min.time()).replace(hour=23, minute=30).astimezone()
    state = {"steps": {"1/a": {"done": True, "source": "manual", "at": local_late.astimezone(UTC).isoformat()}},
             "answers": {}, "checks": {}}
    assert streak(state, date(2026, 11, 24)) == 1
    local_early = local_late.replace(hour=0, minute=10)
    state["steps"]["1/a"]["at"] = local_early.astimezone(UTC).isoformat()
    assert streak(state, date(2026, 11, 24)) == 1
