from servicedesk.catalog import PATTERNS, ROOT_CAUSES, RUNBOOKS, SERVICES, SOURCES


def test_counts():
    assert len(SERVICES) == 12 and len(PATTERNS) == 40 and len(RUNBOOKS) == 12
    assert len({p.id for p in PATTERNS}) == 40


def test_references_resolve():
    ids = {s.id for s in SERVICES}
    assert all(d in ids for s in SERVICES for d in s.depends_on)
    assert all(p.service in ids and p.root_cause in ROOT_CAUSES for p in PATTERNS)
    assert all(p.runbook is None or p.runbook in RUNBOOKS for p in PATTERNS)
    assert all(set(p.sources) <= set(SOURCES) and p.sources for p in PATTERNS)
    assert all(r.service in ids and r.id == key and len(r.steps) >= 3 for key, r in RUNBOOKS.items())


def test_every_service_and_priority_covered():
    assert {p.service for p in PATTERNS} == {s.id for s in SERVICES}
    assert {p.typical_priority for p in PATTERNS} == {1, 2, 3, 4}
    assert {p.root_cause for p in PATTERNS} == set(ROOT_CAUSES)


def test_templates_are_varied():
    for p in PATTERNS:
        assert len(set(p.short_templates)) >= 3 and len(set(p.description_templates)) >= 3, p.id
        assert len(p.resolution_templates) >= 2, p.id


def test_templates_only_use_known_placeholders():
    fill = {"region": "r", "supplier": "s", "error_code": "e", "pct": 1}
    for p in PATTERNS:
        for t in p.short_templates + p.description_templates + p.resolution_templates:
            t.format(**fill)  # raises KeyError on an unknown placeholder


def test_deploy_related_patterns_are_bad_deploys():
    assert all(p.root_cause == "bad-deploy" for p in PATTERNS if p.deploy_related)
    assert sum(p.deploy_related for p in PATTERNS) >= 5
