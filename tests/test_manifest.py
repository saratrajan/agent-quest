import copy

import pytest
from conftest import STEPS, write_lessons

from course.manifest import ManifestError, load_course


def test_course_has_14_sessions_two_phases(tmp_lessons):
    s = load_course(tmp_lessons)
    assert [x.number for x in s] == list(range(1, 15))
    assert [x.phase for x in s].count("Fundamentals") == 5
    assert [x.phase for x in s].count("The agent") == 9


def test_released_session_has_its_steps(tmp_lessons):
    s1 = load_course(tmp_lessons)[0]
    assert s1.released is True and [st["id"] for st in s1.steps] == [st["id"] for st in STEPS]


def test_unreleased_session_has_no_steps(tmp_lessons):
    s2 = load_course(tmp_lessons)[1]
    assert s2.released is False and s2.steps == []


def test_missing_required_key_names_the_key(tmp_path):
    steps = copy.deepcopy(STEPS)
    del steps[0]["youtube_id"]
    with pytest.raises(ManifestError, match="youtube_id"):
        load_course(str(write_lessons(tmp_path, steps)))


def test_unknown_kind_is_rejected(tmp_path):
    steps = copy.deepcopy(STEPS)
    steps[1]["kind"] = "quiz"
    with pytest.raises(ManifestError, match="quiz"):
        load_course(str(write_lessons(tmp_path, steps)))


def test_duplicate_step_id_is_rejected(tmp_path):
    steps = copy.deepcopy(STEPS)
    steps[1]["id"] = "v1"
    with pytest.raises(ManifestError, match="v1"):
        load_course(str(write_lessons(tmp_path, steps)))


def test_real_course_file_loads():
    s = load_course("lessons")
    assert len(s) == 14 and s[0].title == "Tokenization" and s[13].title == "Capstone"
