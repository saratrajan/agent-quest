"""Tests for session 6. Run from the course app, or: pytest lessons/06-baseline -q"""
import os

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.scoring import build_prompt, confusion, majority_baseline, parse_triage, score
else:
    from scoring import build_prompt, confusion, majority_baseline, parse_triage, score

# The five incidents worked through in the lesson.
LABELS = {
    "A": {"priority": 1, "service": "payments"},
    "B": {"priority": 3, "service": "search"},
    "C": {"priority": 3, "service": "search"},
    "D": {"priority": 4, "service": "loyalty"},
    "E": {"priority": 2, "service": "identity"},
}
PREDICTIONS = {
    "A": {"priority": 1, "service": "payments"},   # both right
    "B": {"priority": 2, "service": "search"},     # one level out, service right
    "C": {"priority": 1, "service": "pricing"},    # two levels out, service wrong
    "D": {"priority": 4, "service": "loyalty"},    # both right
    "E": None,                                     # the reply could not be used
}
INCIDENT = {"number": "INC0010401", "short_description": "Refunds taking more than 10 days",
            "description": "Support is getting repeat contacts about refunds that show as pending.",
            "source": "customer-support", "opened_at": "2026-02-01T09:00:00Z", "priority_at_open": 4}
SERVICES = ["search", "payments", "loyalty"]


def test_prompt_carries_the_incident_the_choices_and_the_format():
    prompt = build_prompt(INCIDENT, SERVICES)
    assert INCIDENT["short_description"] in prompt and INCIDENT["description"] in prompt
    assert all(s in prompt for s in SERVICES)
    assert "JSON" in prompt and '"priority"' in prompt and '"service"' in prompt


def test_prompt_changes_with_the_incident_and_the_service_list():
    other = {**INCIDENT, "short_description": "Login loop on mobile", "description": "Users are bounced back to sign-in."}
    assert "Login loop on mobile" in build_prompt(other, SERVICES) and "Refunds" not in build_prompt(other, SERVICES)
    assert "cruises" in build_prompt(INCIDENT, ["cruises"]) and "loyalty" not in build_prompt(INCIDENT, ["cruises"])


def test_parse_accepts_the_shapes_a_model_really_returns():
    assert parse_triage('{"priority": 2, "service": "payments"}') == {"priority": 2, "service": "payments"}
    assert parse_triage('{"priority": "2", "service": " Payments "}') == {"priority": 2, "service": "payments"}
    assert parse_triage('{"priority": "P3", "service": "search", "reason": "slow"}') == {"priority": 3, "service": "search"}


def test_parse_returns_none_instead_of_raising():
    for bad in ["", "I think this is a P2 for payments.", "[1, 2]", '{"priority": 2}', '{"service": "search"}',
                '{"priority": 7, "service": "search"}', '{"priority": "high", "service": "search"}',
                '{"priority": 2, "service": ""}', '{"priority": 2, "service": null}', "null"]:
        assert parse_triage(bad) is None, bad


def test_score_on_the_lesson_example():
    assert score(PREDICTIONS, LABELS) == {"n": 5, "answered": 4, "priority_exact": 0.4,
                                          "priority_within_one": 0.6, "service": 0.6}


def test_a_missing_prediction_counts_as_wrong():
    only_a = {"A": PREDICTIONS["A"]}
    assert score(only_a, LABELS) == {"n": 5, "answered": 1, "priority_exact": 0.2, "priority_within_one": 0.2, "service": 0.2}
    assert score(LABELS, LABELS)["priority_exact"] == 1.0 and score(LABELS, LABELS)["service"] == 1.0


def test_confusion_on_the_lesson_example():
    assert confusion(PREDICTIONS, LABELS) == [
        [1, 0, 0, 0],   # really P1: called P1 once
        [0, 0, 0, 0],   # really P2: the only one was unusable
        [1, 1, 0, 0],   # really P3: called P1 once and P2 once
        [0, 0, 0, 1],   # really P4: called P4 once
    ]


def test_confusion_diagonal_adds_up_to_the_exact_matches():
    table = confusion(PREDICTIONS, LABELS)
    assert sum(table[i][i] for i in range(4)) == round(score(PREDICTIONS, LABELS)["priority_exact"] * 5)
    assert sum(map(sum, table)) == score(PREDICTIONS, LABELS)["answered"]


def test_majority_baseline_on_the_lesson_example():
    assert majority_baseline(LABELS) == {"priority": 3, "service": "search"}
    everyone = {number: majority_baseline(LABELS) for number in LABELS}
    assert score(everyone, LABELS) == {"n": 5, "answered": 5, "priority_exact": 0.4, "priority_within_one": 0.8, "service": 0.4}
