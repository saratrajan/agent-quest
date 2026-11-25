"""Tests for session 9. Run from the course app, or: pytest lessons/09-tool-calling -q

No model is needed: a scripted stand-in plays the model's turns.
"""
import json
import os

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.loop import clip, run_tool, tool_loop, tool_spec
else:
    from loop import clip, run_tool, tool_loop, tool_spec


def call(name, **arguments):
    return {"function": {"name": name, "arguments": arguments}}


def get_service(service_id):
    catalog = {"payments": {"team": "Payments", "depends_on": ["identity"]}}
    return catalog[service_id]


TOOLS = {"get_service": get_service, "add": lambda a, b: int(a) + int(b)}


class Script:
    """Plays the model: returns the next prepared message each time chat is called."""

    def __init__(self, *turns):
        self.turns, self.seen = list(turns), []

    def __call__(self, messages, tools=None):
        self.seen.append({"messages": [dict(m) for m in messages], "tools": tools})
        return {"message": self.turns.pop(0)}


def test_tool_spec_has_the_shape_models_expect():
    spec = tool_spec("get_service", "Look up one service.", {"service_id": "The service id, for example payments."})
    assert spec == {"type": "function", "function": {
        "name": "get_service", "description": "Look up one service.",
        "parameters": {"type": "object",
                       "properties": {"service_id": {"type": "string", "description": "The service id, for example payments."}},
                       "required": ["service_id"]}}}


def test_tool_spec_with_several_arguments_and_with_none():
    two = tool_spec("recent_deploys", "List deploys.", {"service": "Which service.", "before": "A timestamp."})
    assert list(two["function"]["parameters"]["properties"]) == ["service", "before"]
    assert two["function"]["parameters"]["required"] == ["service", "before"]
    none = tool_spec("list_services", "List every service.", {})
    assert none["function"]["parameters"] == {"type": "object", "properties": {}, "required": []}


def test_clip_leaves_short_text_alone_and_marks_what_it_cut():
    assert clip("short", 10) == "short" and clip("exactly10!", 10) == "exactly10!"
    assert clip("abcdefghijklmno", 10) == "abcdefghij\n[cut: 5 more characters]"


def test_run_tool_returns_the_result_as_json():
    assert json.loads(run_tool(call("get_service", service_id="payments"), TOOLS)) == {"team": "Payments", "depends_on": ["identity"]}
    assert run_tool(call("add", a="2", b="3"), TOOLS) == "5"


def test_run_tool_reports_every_kind_of_bad_call_instead_of_raising():
    unknown = json.loads(run_tool(call("delete_everything"), TOOLS))
    assert "delete_everything" in unknown["error"] and "get_service" in unknown["error"] and "add" in unknown["error"]
    assert "error" in json.loads(run_tool(call("get_service", service="payments"), TOOLS))      # misnamed argument
    assert "error" in json.loads(run_tool(call("get_service"), TOOLS))                          # missing argument
    assert "billing" in json.loads(run_tool(call("get_service", service_id="billing"), TOOLS))["error"]   # not found
    assert "error" in json.loads(run_tool({"function": {"name": "get_service", "arguments": None}}, TOOLS))


def test_run_tool_clips_a_long_result():
    tools = {"dump": lambda: "x" * 5000}
    out = run_tool(call("dump"), tools, max_chars=100)
    assert len(out) < 140 and out.endswith("more characters]")


def test_loop_returns_at_once_when_the_model_just_answers():
    chat = Script({"role": "assistant", "content": "Hello."})
    messages = [{"role": "user", "content": "Hi"}]
    assert tool_loop(messages, TOOLS, [], chat) == "Hello."
    assert len(chat.seen) == 1 and messages[-1] == {"role": "assistant", "content": "Hello."}


def test_loop_runs_a_tool_and_feeds_the_result_back():
    specs = [tool_spec("get_service", "Look up one service.", {"service_id": "The id."})]
    chat = Script({"role": "assistant", "content": "", "tool_calls": [call("get_service", service_id="payments")]},
                  {"role": "assistant", "content": "Payments is owned by the Payments team."})
    messages = [{"role": "user", "content": "Who owns payments?"}]
    assert tool_loop(messages, TOOLS, specs, chat) == "Payments is owned by the Payments team."
    assert [m["role"] for m in messages] == ["user", "assistant", "tool", "assistant"]
    assert messages[2]["tool_name"] == "get_service" and json.loads(messages[2]["content"])["team"] == "Payments"
    assert chat.seen[0]["tools"] == specs
    assert [m["role"] for m in chat.seen[1]["messages"]] == ["user", "assistant", "tool"]   # the second turn saw the result


def test_loop_handles_several_calls_in_one_turn_and_a_failing_one():
    chat = Script({"role": "assistant", "content": "", "tool_calls": [call("add", a="1", b="2"), call("nope")]},
                  {"role": "assistant", "content": "", "tool_calls": [call("add", a="3", b="4")]},
                  {"role": "assistant", "content": "3 and 7."})
    messages = [{"role": "user", "content": "Add things"}]
    assert tool_loop(messages, TOOLS, [], chat) == "3 and 7."
    results = [m for m in messages if m["role"] == "tool"]
    assert [r["content"] for r in results[::2]] == ["3", "7"] and "error" in results[1]["content"]


def test_loop_stops_after_max_steps_and_returns_none():
    forever = [{"role": "assistant", "content": "", "tool_calls": [call("add", a="1", b="1")]} for _ in range(10)]
    chat = Script(*forever)
    messages = [{"role": "user", "content": "Loop"}]
    assert tool_loop(messages, TOOLS, [], chat, max_steps=3) is None
    assert len(chat.seen) == 3 and sum(m["role"] == "tool" for m in messages) == 3
