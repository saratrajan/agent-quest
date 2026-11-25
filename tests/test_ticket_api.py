import pytest
from fastapi.testclient import TestClient

from servicedesk.app import create_app
from servicedesk.catalog import PATTERNS

T = "/api/now/table/incident"
HIDDEN = {"priority", "service", "assignment_group", "root_cause_category", "resolution", "resolved_at", "duplicate_of", "close_code"}


@pytest.fixture
def client(db_path):
    return TestClient(create_app(db_path=db_path))


def test_list_is_history_only_newest_first_and_paged(client):
    r = client.get(f"{T}?limit=5").json()
    assert r["total"] == 400 and len(r["result"]) == 5
    assert r["result"][0]["number"] == "INC0010400" and r["result"][4]["number"] == "INC0010396"
    assert not {"pattern_id", "split", "is_vague"} & set(r["result"][0])
    assert client.get(f"{T}?limit=5&offset=5").json()["result"][0]["number"] == "INC0010395"


def test_filters(client):
    r = client.get(f"{T}?priority=1&limit=100").json()
    assert r["result"] and all(i["priority"] == 1 for i in r["result"]) and r["total"] == len(r["result"])
    r = client.get(f"{T}?service=payments&source=monitoring&limit=100").json()
    assert r["result"] and all(i["service"] == "payments" and i["source"] == "monitoring" for i in r["result"])
    r = client.get(f"{T}?q=CERTIFICATE&limit=100").json()
    assert r["result"] and all("certificate" in (i["short_description"] + i["description"]).lower() for i in r["result"])
    r = client.get(f"{T}?opened_before=2025-09-01T00:00:00Z&limit=100").json()
    assert r["result"] and all(i["opened_at"] < "2025-09-01T00:00:00Z" for i in r["result"])


def test_search_text_is_not_treated_as_sql_or_wildcards(client):
    assert client.get(f"{T}?q=%25").json()["total"] < 400
    assert client.get(f"{T}?q=' OR 1=1 --").json()["total"] == 0


def test_history_incident_has_everything(client, generated):
    src = generated[0][10]
    r = client.get(f"{T}/{src['number']}").json()["result"]
    assert r["resolution"] == src["resolution"] and r["priority"] == src["priority"]
    assert [n["text"] for n in r["work_notes"]] == [n["text"] for n in src["work_notes"]]


def test_eval_incident_hides_answers(client):
    r = client.get(f"{T}/INC0010450").json()["result"]
    assert not HIDDEN & set(r) and r["work_notes"] == [] and r["short_description"]


def test_eval_list(client):
    r = client.get("/api/eval/incidents").json()
    assert r["total"] == 100 and len(r["result"]) == 100
    assert set(r["result"][0]) == {"number", "short_description", "description", "source", "opened_at", "priority_at_open"}


def test_create_and_note(client):
    r = client.post(T, json={"short_description": "x", "description": "y", "source": "employee"})
    assert r.status_code == 201
    n = r.json()["result"]["number"]
    assert n == "INC0010501" and r.json()["result"]["state"] == "New"
    assert client.post(f"{T}/{n}/work_notes", json={"author": "triage-agent", "text": "hi"}).status_code == 201
    got = client.get(f"{T}/{n}").json()["result"]
    assert got["work_notes"][0]["text"] == "hi" and got["work_notes"][0]["author"] == "triage-agent"
    assert client.get(f"{T}?limit=1").json()["result"][0]["number"] == n


def test_note_on_eval_incident_is_visible(client):
    client.post(f"{T}/INC0010450/work_notes", json={"author": "triage-agent", "text": "proposed P2"})
    assert [n["text"] for n in client.get(f"{T}/INC0010450").json()["result"]["work_notes"]] == ["proposed P2"]


def test_bad_input_is_rejected(client):
    assert client.post(T, json={"short_description": "x", "description": "y", "source": "telepathy"}).status_code == 422
    assert client.post(T, json={"short_description": "", "description": "y", "source": "employee"}).status_code == 422
    assert client.post(f"{T}/INC0010001/work_notes", json={"author": "a", "text": ""}).status_code == 422
    assert client.get(f"{T}?priority=9").status_code == 422
    assert len(client.get(f"{T}?limit=1000").json()["result"]) == 100


def test_unknown_is_404(client):
    for url in [f"{T}/INC9999999", "/api/services/nope", "/api/runbooks/nope"]:
        r = client.get(url)
        assert r.status_code == 404 and "detail" in r.json()
    assert client.post(f"{T}/INC9999999/work_notes", json={"author": "a", "text": "b"}).status_code == 404


def test_services_and_runbooks(client):
    assert client.get("/api/services").json()["total"] == 12
    s = client.get("/api/services/payments").json()["result"]
    assert s["team"] == "Payments" and "identity" in s["depends_on"]
    rb = client.get("/api/runbooks/rb-cert-renewal").json()["result"]
    assert rb["title"] and len(rb["steps"]) >= 3


def test_deploys_window(client, generated):
    deploy_related = {p.id for p in PATTERNS if p.deploy_related}
    inc = next(i for i in generated[0] if i["pattern_id"] in deploy_related and i["split"] == "history")
    r = client.get("/api/deploys", params={"service": inc["service"], "before": inc["opened_at"], "hours": 2}).json()
    assert r["total"] >= 1 and all(d["service"] == inc["service"] and d["deployed_at"] <= inc["opened_at"] for d in r["result"])
    assert client.get("/api/deploys", params={"service": inc["service"], "before": "2020-01-01T00:00:00Z"}).json()["total"] == 0


def test_missing_database_says_how_to_fix_it(tmp_path):
    c = TestClient(create_app(db_path=str(tmp_path / "nope.db")))
    r = c.get(T)
    assert r.status_code == 503 and "make data" in r.json()["detail"]


def test_eval_incident_does_not_reveal_that_it_was_resolved(client):
    assert client.get(f"{T}/INC0010450").json()["result"]["state"] == "New"


def test_notes_carry_roles_and_api_notes_may_set_one(client, generated):
    src = generated[0][10]
    notes = client.get(f"{T}/{src['number']}").json()["result"]["work_notes"]
    assert notes[0]["role"] == "Service desk" and len(notes) == len(src["work_notes"])
    client.post(f"{T}/INC0010450/work_notes", json={"author": "triage-agent", "role": "Automated triage", "text": "x"})
    client.post(f"{T}/INC0010450/work_notes", json={"author": "someone", "text": "y"})
    got = client.get(f"{T}/INC0010450").json()["result"]["work_notes"]
    assert [n["role"] for n in got] == ["Automated triage", ""]
