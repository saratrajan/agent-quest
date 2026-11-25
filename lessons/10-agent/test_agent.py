"""Tests for session 10. Run from the course app, or: pytest lessons/10-agent -q

No model is needed: scripted stand-ins play the model's turns.
"""
import os

import pytest

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.agent import COMMIT, CONFIDENCE, SYSTEM, answer_schema, check_answer, traced, triage
else:
    from agent import COMMIT, CONFIDENCE, SYSTEM, answer_schema, check_answer, traced, triage

SERVICES = ["payments", "search", "identity"]
INCIDENT = {"number": "INC0010401", "opened_at": "2026-07-26T00:58:41Z", "source": "customer-support", "priority_at_open": 4,
            "short_description": "Refunds taking more than 10 days", "description": "The refund backlog has doubled this week."}
GOOD = {"priority": 3, "service": "payments", "similar_incidents": ["INC0010011", "INC0010044"],
        "probable_cause": "Refund batch capacity.", "first_steps": ["Check the refund queue depth."], "confidence": "medium"}


def call(name, **arguments):
    return {"role": "assistant", "content": "", "thought": "look it up", "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}


class Script:
    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []

    def __call__(self, messages, tools=None):
        self.seen.append([dict(m) for m in messages])
        return {"message": self.turns.pop(0)}


def test_schema_has_the_six_fields_all_required():
    schema = answer_schema(SERVICES)
    assert schema["type"] == "object"
    assert list(schema["properties"]) == ["priority", "service", "similar_incidents", "probable_cause", "first_steps", "confidence"]
    assert schema["required"] == list(schema["properties"])


def test_schema_enums_make_the_answer_checkable():
    p = answer_schema(SERVICES)["properties"]
    assert p["priority"] == {"type": "integer", "enum": [1, 2, 3, 4]}
    assert p["service"] == {"type": "string", "enum": SERVICES}
    assert p["confidence"] == {"type": "string", "enum": CONFIDENCE} and "not enough information" in CONFIDENCE
    assert p["similar_incidents"] == {"type": "array", "items": {"type": "string"}, "maxItems": 3}
    assert p["first_steps"]["maxItems"] == 4 and p["probable_cause"] == {"type": "string"}
    assert answer_schema(["cruises"])["properties"]["service"]["enum"] == ["cruises"]


def test_traced_records_each_call_and_returns_the_result_unchanged():
    trace = []
    tools = traced({"double": lambda n: n * 2, "greet": lambda name: f"hello {name}"}, trace)
    assert tools["double"](n=4) == 8 and tools["greet"](name="Asha") == "hello Asha"   # each wrapper calls its own tool
    assert [(t["tool"], t["arguments"], t["result"]) for t in trace] == [("double", {"n": 4}, 8), ("greet", {"name": "Asha"}, "hello Asha")]
    assert all(isinstance(t["seconds"], float) and t["seconds"] >= 0 for t in trace)


def test_traced_records_a_failure_and_still_raises_it():
    trace = []

    def missing(number):
        raise LookupError(f"There is no incident {number}")

    tools = traced({"get_incident": missing}, trace)
    with pytest.raises(LookupError):
        tools["get_incident"](number="INC9")
    assert trace[0]["error"] == "There is no incident INC9" and "result" not in trace[0] and "seconds" in trace[0]


def test_check_answer_passes_a_sound_answer_and_flags_a_missing_one():
    assert check_answer(GOOD, SERVICES, {"INC0010011", "INC0010044", "INC0010301"}) == []
    assert check_answer(None, SERVICES, set()) == ["no answer"]


def test_check_answer_names_each_problem():
    bad = {**GOOD, "priority": 7, "service": "billing", "similar_incidents": ["INC0010011", "INC0099999", "INC0088888"]}
    assert check_answer(bad, SERVICES, {"INC0010011"}) == ["priority out of range", "unknown service",
                                                           "invented incident INC0099999", "invented incident INC0088888"]
    assert check_answer({"priority": 2, "service": "search"}, SERVICES, set()) == []      # no similar incidents cited is allowed
    assert check_answer({}, SERVICES, set()) == ["priority out of range", "unknown service"]


def test_triage_investigates_then_commits():
    found = {"incidents": [{"number": "INC0010011", "priority": 3, "service": "payments"}]}
    step = Script(call("search_incidents", query="refund backlog"), {"role": "assistant", "content": "Looks like the refund batch again."})
    committed = {}

    def commit(messages, schema):
        committed.update(messages=[dict(m) for m in messages], schema=schema)
        return GOOD

    out = triage(INCIDENT, {"search_incidents": lambda query: found}, [], SERVICES, step, commit)
    assert out["answer"] == GOOD and out["finished"] is True
    assert [(t["tool"], t["arguments"], t["result"]) for t in out["trace"]] == [("search_incidents", {"query": "refund backlog"}, found)]
    first = step.seen[0]
    assert first[0] == {"role": "system", "content": SYSTEM} and first[1]["role"] == "user"
    for value in ("INC0010401", "2026-07-26T00:58:41Z", "customer-support", "Refunds taking more than 10 days", "The refund backlog has doubled"):
        assert value in first[1]["content"], value
    assert committed["schema"] == answer_schema(SERVICES)
    assert committed["messages"][-1] == {"role": "user", "content": COMMIT}
    assert [m["role"] for m in out["messages"]] == ["system", "user", "assistant", "tool", "assistant", "user"]


def test_triage_still_commits_when_the_loop_runs_out_of_steps():
    step = Script(*[call("search_incidents", query="x") for _ in range(5)])
    out = triage(INCIDENT, {"search_incidents": lambda query: {"incidents": []}}, [], SERVICES, step, lambda m, s: GOOD, max_steps=2)
    assert out["finished"] is False and out["answer"] == GOOD and len(out["trace"]) == 2


def test_triage_passes_on_a_missing_answer_and_records_failed_tools():
    def broken(query):
        raise RuntimeError("search is down")

    step = Script(call("search_incidents", query="refund"), {"role": "assistant", "content": "I could not search."})
    out = triage(INCIDENT, {"search_incidents": broken}, [], SERVICES, step, lambda m, s: None)
    assert out["answer"] is None and out["trace"][0]["error"] == "search is down"
    assert "search is down" in out["messages"][3]["content"]     # the model was told, through the tool result
