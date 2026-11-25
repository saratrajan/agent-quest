from collections import Counter
from datetime import datetime, timedelta

from servicedesk.catalog import PATTERNS, SERVICES
from servicedesk.generate import build_deploys, build_incidents, export_corpus

INC = build_incidents()
BY = {i["number"]: i for i in INC}
PAT = {p.id: p for p in PATTERNS}


def t(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


def test_deterministic():
    assert build_incidents() == INC and build_deploys() == build_deploys()
    assert build_incidents(seed=1) != INC


def test_shape_and_split():
    assert len(INC) == 500 and [i["number"] for i in INC] == [f"INC{10001 + k:07d}" for k in range(500)]
    assert [i["opened_at"] for i in INC] == sorted(i["opened_at"] for i in INC)
    assert [i["split"] for i in INC] == ["history"] * 400 + ["eval"] * 100
    assert "2025-05-20" <= INC[0]["opened_at"] and INC[-1]["opened_at"] < "2026-11-21"
    keys = {"number", "short_description", "description", "source", "opened_at", "resolved_at", "priority_at_open",
            "priority", "service", "assignment_group", "root_cause_category", "pattern_id", "duplicate_of", "state",
            "resolution", "close_code", "work_notes", "is_vague", "split"}
    assert all(set(i) == keys for i in INC)


def test_fields_agree_with_the_catalog():
    teams = {s.id: s.team for s in SERVICES}
    for i in INC:
        p = PAT[i["pattern_id"]]
        assert i["service"] == p.service and i["root_cause_category"] == p.root_cause
        assert i["assignment_group"] == teams[p.service] and i["source"] in p.sources
        assert i["state"] == "Resolved" and i["resolved_at"] > i["opened_at"] and len(i["work_notes"]) >= 2
        assert "{" not in i["short_description"] + i["description"] + i["resolution"]


def test_priority_mix():
    assert Counter(i["priority"] for i in INC) == {1: 25, 2: 75, 3: 225, 4: 175}
    assert all(0 <= i["priority"] - PAT[i["pattern_id"]].typical_priority <= 1 for i in INC)


def test_mess():
    wrong = [i for i in INC if i["priority_at_open"] != i["priority"]]
    assert len(wrong) == 75 and all(abs(i["priority_at_open"] - i["priority"]) == 1 for i in wrong)
    assert all(1 <= i["priority_at_open"] <= 4 for i in INC)
    assert sum(i["duplicate_of"] is not None for i in INC) == 40
    assert sum(i["is_vague"] for i in INC) == 50


def test_vague_incidents_withhold_the_giveaways():
    names = {s.id: s.name for s in SERVICES}
    for i in (x for x in INC if x["is_vague"]):
        assert len(i["short_description"].split()) < 6
        text = (i["short_description"] + " " + i["description"]).lower()
        assert names[i["service"]].lower() not in text and i["service"] not in text
        assert "error code" not in text


def test_duplicates_point_back_to_same_pattern_within_six_hours():
    for i in INC:
        if i["duplicate_of"]:
            o = BY[i["duplicate_of"]]
            assert o["pattern_id"] == i["pattern_id"] and o["duplicate_of"] is None
            assert timedelta(0) < t(i["opened_at"]) - t(o["opened_at"]) <= timedelta(hours=6)
            assert o["number"] in i["resolution"]


def test_patterns_recur_in_history():
    c = Counter(i["pattern_id"] for i in INC if i["split"] == "history")
    assert len(c) == 40 and min(c.values()) >= 5


def test_deploy_related_incidents_have_a_deploy():
    deploys = build_deploys()
    assert 250 <= len(deploys) <= 350 and [d["deployed_at"] for d in deploys] == sorted(d["deployed_at"] for d in deploys)
    assert len({d["id"] for d in deploys}) == len(deploys)
    for i in INC:
        if PAT[i["pattern_id"]].deploy_related:
            assert any(d["service"] == i["service"] and timedelta(0) <= t(i["opened_at"]) - t(d["deployed_at"]) <= timedelta(hours=2)
                       for d in deploys), i["number"]


def test_corpus_excludes_eval():
    text = export_corpus(INC)
    assert INC[0]["description"] in text and INC[399]["resolution"] in text
    assert all(i["number"] not in text for i in INC[400:])
    assert INC[0]["number"] in text


def test_eval_labels_list_the_history_incidents_with_the_same_cause():
    from servicedesk.generate import eval_labels
    labels = eval_labels(INC)
    assert len(labels) == 100 and set(labels) == {i["number"] for i in INC[400:]}
    for number, label in labels.items():
        assert label["priority"] == BY[number]["priority"] and label["service"] == BY[number]["service"]
        assert label["related"], number  # every pattern recurs in history
        for other in label["related"]:
            assert BY[other]["split"] == "history" and BY[other]["pattern_id"] == BY[number]["pattern_id"]
    one = next(iter(labels.values()))
    assert len(one["related"]) == sum(i["split"] == "history" and i["pattern_id"] == one["pattern_id"] for i in INC)


def test_existing_data_gets_the_newer_labels_without_touching_the_database(tmp_path):
    import json
    from servicedesk.generate import main
    main(str(tmp_path))
    db = tmp_path / "timetravel.db"
    before = db.stat().st_mtime_ns
    old = {k: {f: v for f, v in label.items() if f != "related"} for k, label in json.loads((tmp_path / "eval_labels.json").read_text()).items()}
    (tmp_path / "eval_labels.json").write_text(json.dumps(old))
    main(str(tmp_path), if_missing=True)
    assert "related" in json.loads((tmp_path / "eval_labels.json").read_text())["INC0010401"]
    assert db.stat().st_mtime_ns == before
