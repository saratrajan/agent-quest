"""Each resolved incident carries a realistic troubleshooting thread."""
from datetime import datetime

from servicedesk.catalog import PATTERNS
from servicedesk.generate import build_incidents
from servicedesk.troubleshooting import CHECKS

INC = build_incidents()
PAT = {p.id: p for p in PATTERNS}
WORKED = [i for i in INC if not i["duplicate_of"]]


def t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def test_every_pattern_has_three_specific_checks_with_valid_placeholders():
    assert set(CHECKS) == set(PAT)
    fill = {"region": "r", "supplier": "s", "error_code": "e", "pct": 1}
    for pid, checks in CHECKS.items():
        assert len(set(checks)) == 3, pid
        for c in checks:
            c.format(**fill)


def test_threads_are_long_enough_and_grow_with_severity():
    assert all(len(i["work_notes"]) >= 7 for i in WORKED)
    assert all(len(i["work_notes"]) >= 10 for i in WORKED if i["priority"] <= 2)
    assert max(len(i["work_notes"]) for i in INC) <= 16


def test_several_people_with_roles_contribute():
    for i in WORKED:
        assert len({n["author"] for n in i["work_notes"]}) >= 3, i["number"]
        assert all(set(n) == {"at", "author", "role", "text"} and n["role"] and n["text"] for n in i["work_notes"])
        roles = {n["role"] for n in i["work_notes"]}
        assert "Service desk" in roles and any("on-call" in r for r in roles), i["number"]


def test_timestamps_run_forward_from_open_to_resolution():
    for i in INC:
        times = [t(n["at"]) for n in i["work_notes"]]
        assert times == sorted(times) and len(set(times)) == len(times), i["number"]
        assert times[0] > t(i["opened_at"]) and times[-1] == t(i["resolved_at"]), i["number"]


def test_thread_contains_the_patterns_own_diagnostics():
    fill = lambda c: c.split("{")[0][:25]  # text before the first placeholder
    for i in WORKED:
        text = " ".join(n["text"] for n in i["work_notes"])
        hits = sum(fill(c) in text for c in CHECKS[i["pattern_id"]])
        assert hits >= 2, i["number"]


def test_major_incidents_have_a_commander_and_customer_updates():
    for i in WORKED:
        roles = [n["role"] for n in i["work_notes"]]
        if i["priority"] == 1:
            assert "Incident commander" in roles and "Customer support" in roles, i["number"]


def test_supplier_problems_involve_supplier_relations():
    for i in WORKED:
        if i["root_cause_category"] == "supplier-api":
            assert "Supplier relations" in [n["role"] for n in i["work_notes"]], i["number"]


def test_vague_incidents_get_clarified_in_the_thread():
    for i in WORKED:
        if i["is_vague"]:
            assert any(n["role"] == "Reporter" for n in i["work_notes"]), i["number"]


def test_a_wrong_first_guess_is_recorded_and_ruled_out():
    assert all(any("Ruled out" in n["text"] for n in i["work_notes"]) for i in WORKED)


def test_resolution_states_cause_fix_and_follow_up():
    for i in WORKED:
        r = i["resolution"]
        assert r.startswith("Root cause: ") and " Fix: " in r and " Follow-up: " in r, i["number"]
        assert i["close_code"] in {"Solved (permanently)", "Solved (workaround)", "Not reproducible"}
        assert i["work_notes"][-1]["text"] == r
    for i in INC:
        if i["duplicate_of"]:
            assert i["close_code"] == "Duplicate" and 3 <= len(i["work_notes"]) <= 5


def test_threads_are_deterministic_and_varied():
    assert build_incidents() == INC
    same_pattern = [i for i in WORKED if i["pattern_id"] == "payments-3ds-timeout"]
    assert len({tuple(n["text"] for n in i["work_notes"]) for i in same_pattern}) == len(same_pattern)
