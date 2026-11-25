import re
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from servicedesk.app import create_app
from servicedesk.catalog import PATTERNS


def t(x):
    return datetime.strptime(x, "%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture
def desk(db_path):
    return TestClient(create_app(db_path=db_path))


def test_home_is_a_summary_built_from_real_data(desk, generated):
    h = desk.get("/").text
    assert 'data-kpi="open">100<' in h and "Avg resolution time" in h and "Incidents (30d)" in h
    counts = [int(x) for x in re.findall(r'data-open-priority="\d">(\d+)<', h)]
    assert len(counts) == 4 and sum(counts) == 100
    assert h.count('data-recent="') == 5 and 'href="/incidents/INC0010500"' in h
    assert "98.7" not in h  # nothing on the page is invented


def test_stats_match_the_generated_data(db_path, generated):
    from servicedesk.api import Tickets
    s = Tickets(db_path).stats()
    hist = [i for i in generated[0] if i["split"] == "history"]
    mins = [(t(i["resolved_at"]) - t(i["opened_at"])).total_seconds() / 60 for i in hist]
    assert s["open"] == 100 and s["resolved"] == 400
    assert abs(s["avg_resolution_minutes"] - sum(mins) / len(mins)) < 1
    assert s["reprioritised_pct"] == round(100 * sum(i["priority_at_open"] != i["priority"] for i in hist) / 400)
    assert s["last_30_days"] + s["prior_30_days"] <= 500 and s["last_30_days"] > 0


def test_open_queue_lists_untriaged_incidents_without_answers(desk):
    h = desk.get("/incidents?view=open").text
    assert "100 incidents" in h and "INC0010500" in h and h.count('data-incident="') == 25
    assert 'class="priority p' not in h and "Unassigned" in h


def test_resolved_view_shows_25_newest_with_priorities(desk):
    h = desk.get("/incidents?view=resolved").text
    assert h.count('data-incident="') == 25 and "INC0010400" in h and "400 incidents" in h
    assert 'href="/incidents/INC0010400"' in h and 'class="priority p' in h


def test_all_view_counts_everything(desk):
    assert "500 incidents" in desk.get("/incidents?view=all").text


def test_filters_and_paging(desk):
    h = desk.get("/incidents?view=resolved&priority=1").text
    assert 'class="priority p1"' in h and 'class="priority p3"' not in h
    h2 = desk.get("/incidents?view=resolved&page=2").text
    assert "INC0010375" in h2 and "INC0010400" not in h2
    assert "No incidents match" in desk.get("/incidents?view=resolved&q=zzzzqqqq").text


def test_detail_shows_fields_notes_and_related_deploys(desk, generated):
    related = {p.id for p in PATTERNS if p.deploy_related}
    inc = next(i for i in generated[0] if i["pattern_id"] in related and i["split"] == "history" and not i["duplicate_of"])
    h = desk.get(f"/incidents/{inc['number']}").text
    assert inc["number"] in h and "Resolution" in h and f"{inc['service']}-v3." in h
    assert inc["assignment_group"] in h
    assert inc["work_notes"][0]["author"] in desk.get(f"/incidents/{inc['number']}?tab=timeline").text


def test_open_incident_detail_hides_answers(desk):
    h = desk.get("/incidents/INC0010450").text
    assert "Resolution" not in h and "Unassigned" in h and "New" in h


def test_add_a_work_note_from_the_page(desk):
    r = desk.post("/incidents/INC0010450/notes", data={"author": "Sarat", "text": "Looking into <this>"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/incidents/INC0010450"
    h = desk.get("/incidents/INC0010450").text
    assert "Looking into &lt;this&gt;" in h and "Sarat" in h


def test_agent_notes_are_marked(desk):
    desk.post("/api/now/table/incident/INC0010001/work_notes", json={"author": "triage-agent", "text": "Proposed P2"})
    h = desk.get("/incidents/INC0010001").text
    assert 'class="note agent"' in h and "Proposed P2" in h


def test_create_an_incident_from_the_form(desk):
    assert "Short description" in desk.get("/incidents/new").text
    r = desk.post("/incidents/new", data={"short_description": "Checkout is slow", "description": "Since noon", "source": "employee"},
                  follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/incidents/INC0010501"
    assert "Checkout is slow" in desk.get("/incidents?view=open").text


def test_form_rejects_empty_or_invalid_input_and_keeps_what_was_typed(desk):
    r = desk.post("/incidents/new", data={"short_description": "", "description": "Something typed", "source": "employee"})
    assert r.status_code == 422 and "Something typed" in r.text and "short description" in r.text.lower()
    r = desk.post("/incidents/new", data={"short_description": "x", "description": "y", "source": "telepathy"})
    assert r.status_code == 422
    assert desk.post("/incidents/INC0010450/notes", data={"author": "a", "text": "  "}, follow_redirects=False).status_code == 422


def test_services_and_runbook_pages(desk):
    h = desk.get("/services").text
    assert h.count('data-service="') == 12 and "Supplier Integrations" in h
    rb = desk.get("/runbooks/rb-cert-renewal").text
    assert "Renew an expired or expiring certificate" in rb and rb.count("<li") >= 5


def test_unknown_things_are_404(desk):
    for url in ["/incidents/INC9999999", "/runbooks/nope"]:
        assert desk.get(url).status_code == 404
    assert desk.post("/incidents/INC9999999/notes", data={"author": "a", "text": "b"}).status_code == 404


def test_pages_explain_missing_data(tmp_path):
    c = TestClient(create_app(db_path=str(tmp_path / "nope.db")))
    r = c.get("/incidents")
    assert r.status_code == 200 and "make data" in r.text


def test_activity_shows_each_authors_role_and_the_close_code(desk, generated):
    inc = next(i for i in generated[0] if i["split"] == "history" and i["priority"] == 1 and not i["duplicate_of"])
    assert inc["close_code"] in desk.get(f"/incidents/{inc['number']}").text
    h = desk.get(f"/incidents/{inc['number']}?tab=timeline").text
    assert "Incident commander" in h and "Service desk" in h
    assert h.count('<div class="note') == len(inc["work_notes"])


# --- the tabbed incident page

def worked(generated, **want):
    return next(i for i in generated[0] if i["split"] == "history" and not i["duplicate_of"]
                and all(i[k] == v for k, v in want.items()))


def test_overview_shows_only_the_latest_updates_with_a_link_to_the_rest(desk, generated):
    inc = worked(generated, priority=1)
    h = desk.get(f"/incidents/{inc['number']}").text
    assert h.count('<div class="note') == 3 and f'href="/incidents/{inc["number"]}?tab=timeline"' in h
    assert inc["work_notes"][-1]["text"][:40] in h and 'aria-current="page">Overview' in h


def test_status_steps_reflect_how_far_the_incident_got(desk, generated):
    inc = worked(generated, priority=2)
    assert desk.get(f"/incidents/{inc['number']}").text.count('data-step-done="true"') == 4
    h = desk.get("/incidents/INC0010450").text
    assert h.count('data-step-done="true"') == 1 and h.count('data-step-done="false"') == 3


def test_timeline_tab_has_the_note_form(desk):
    h = desk.get("/incidents/INC0010450?tab=timeline").text
    assert 'action="/incidents/INC0010450/notes"' in h and 'aria-current="page">Timeline' in h


def test_related_tab_links_duplicates_and_same_service_neighbours(desk, generated):
    dup = next(i for i in generated[0] if i["duplicate_of"] and i["split"] == "history")
    assert f'href="/incidents/{dup["duplicate_of"]}"' in desk.get(f"/incidents/{dup['number']}?tab=related").text
    assert f'href="/incidents/{dup["number"]}"' in desk.get(f"/incidents/{dup['duplicate_of']}?tab=related").text


def test_services_and_knowledge_tabs(desk, generated):
    inc = worked(generated, service="payments", root_cause_category="dependency-outage")
    h = desk.get(f"/incidents/{inc['number']}?tab=services").text
    assert "Payments" in h and "identity" in h and "Tier 1" in h
    assert "Fail over to the secondary payment gateway" in desk.get(f"/incidents/{inc['number']}?tab=knowledge").text


def test_open_incident_tabs_reveal_nothing(desk):
    for tab in ["related", "services", "knowledge"]:
        h = desk.get(f"/incidents/INC0010450?tab={tab}").text
        assert "not been triaged" in h and "rb-" not in h and 'href="/incidents/INC00' not in h.split("<main")[1]


def test_unknown_tab_falls_back_to_overview(desk):
    assert 'aria-current="page">Overview' in desk.get("/incidents/INC0010001?tab=nonsense").text


def test_overview_links_the_runbook_that_fits_this_incident(desk, generated):
    inc = worked(generated, service="payments", root_cause_category="dependency-outage")
    h = desk.get(f"/incidents/{inc['number']}").text
    assert "Fail over to the secondary payment gateway" in h and "Roll back a bad deploy" not in h
