"""The plumbing for sessions 6 to 10, tested against stand-in servers: no model and no desk needed."""
import json
import socketserver
import sys
import threading
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("lessons").resolve()))
import agentkit  # noqa: E402


def serve(routes):
    """routes: function(method, path, body) -> (status, reply dict). Returns (url, list of calls seen)."""
    seen = []

    class Handler(BaseHTTPRequestHandler):
        def _go(self, method):
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n)) if n else None
            seen.append((method, self.path, body))
            status, reply = routes(method, self.path, body)
            self.send_response(status); self.end_headers(); self.wfile.write(json.dumps(reply).encode())

        def do_GET(self):
            self._go("GET")

        def do_POST(self):
            self._go("POST")

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}", seen


@pytest.fixture
def fake():
    started = []

    def start(routes):
        httpd, url, seen = serve(routes)
        started.append(httpd)
        return url, seen

    yield start
    for h in started:
        h.shutdown()


def test_desk_reads_and_posts_json(fake):
    url, seen = fake(lambda m, p, b: (200, {"result": {"number": "INC1", "echo": b}}))
    assert agentkit.desk("/api/now/table/incident/INC1", host=url)["result"]["number"] == "INC1"
    agentkit.desk("/api/now/table/incident/INC1/work_notes", {"author": "a", "text": "t"}, host=url)
    assert seen[1] == ("POST", "/api/now/table/incident/INC1/work_notes", {"author": "a", "text": "t"})


def test_desk_down_says_how_to_start_it():
    with pytest.raises(RuntimeError, match="make desk"):
        agentkit.desk("/api/services", host="http://127.0.0.1:9")


def test_desk_error_carries_the_desks_own_message(fake):
    url, _ = fake(lambda m, p, b: (404, {"detail": "There is no incident INC9"}))
    with pytest.raises(LookupError, match="There is no incident INC9"):
        agentkit.desk("/api/now/table/incident/INC9", host=url)


def test_history_pages_through_resolved_incidents_and_skips_open_ones(fake):
    rows = [{"number": f"INC{i}", "resolution": "fixed", "priority": 3} for i in range(230)] + [{"number": "LIVE1", "state": "New"}]

    def routes(method, path, body):
        offset = int(path.split("offset=")[1].split("&")[0])
        return 200, {"result": rows[offset:offset + 100], "total": len(rows)}

    url, seen = fake(routes)
    got = agentkit.history(host=url)
    assert len(got) == 230 and len(seen) == 3 and all("resolution" in g for g in got)


def test_ask_sends_a_direct_json_request_and_times_it(fake):
    url, seen = fake(lambda m, p, b: (200, {"response": ' {"priority": 2} ', "prompt_eval_count": 40, "eval_count": 9}))
    r = agentkit.ask("triage this", host=url, temperature=0)
    body = seen[0][2]
    assert r["text"] == '{"priority": 2}' and r["prompt_tokens"] == 40 and r["output_tokens"] == 9 and r["seconds"] >= 0
    assert body["think"] is False and body["format"] == "json" and body["stream"] is False
    assert body["options"] == {"temperature": 0}


def test_ask_can_take_a_schema_as_the_format(fake):
    url, seen = fake(lambda m, p, b: (200, {"response": "{}"}))
    schema = {"type": "object", "properties": {"priority": {"type": "integer"}}}
    agentkit.ask("x", host=url, schema=schema)
    assert seen[0][2]["format"] == schema


def test_chat_passes_tools_and_returns_the_message(fake):
    call = {"function": {"name": "get_incident", "arguments": {"number": "INC1"}}}
    url, seen = fake(lambda m, p, b: (200, {"message": {"role": "assistant", "content": "", "tool_calls": [call]},
                                           "prompt_eval_count": 100, "eval_count": 20}))
    tools = [{"type": "function", "function": {"name": "get_incident"}}]
    r = agentkit.chat([{"role": "user", "content": "hi"}], tools=tools, host=url)
    assert r["message"]["tool_calls"] == [call] and r["prompt_tokens"] == 100 and r["output_tokens"] == 20
    assert seen[0][1] == "/api/chat" and seen[0][2]["tools"] == tools and seen[0][2]["think"] is False


def test_embed_batches_and_keeps_order(fake):
    def routes(method, path, body):
        return 200, {"embeddings": [[float(len(t)), 1.0] for t in body["input"]]}

    url, seen = fake(routes)
    texts = ["a" * (i + 1) for i in range(70)]
    vectors = agentkit.embed(texts, host=url, batch=32)
    assert [v[0] for v in vectors] == [float(i + 1) for i in range(70)] and len(seen) == 3


def test_model_errors_say_what_to_do(fake):
    url, _ = fake(lambda m, p, b: (404, {"error": "model not found"}))
    with pytest.raises(RuntimeError, match="ollama pull nomic-embed-text"):
        agentkit.embed(["x"], host=url)
    with pytest.raises(RuntimeError, match="ollama serve"):
        agentkit.ask("x", host="http://127.0.0.1:9", timeout=2)


def test_eval_labels_missing_says_make_data(tmp_path):
    with pytest.raises(SystemExit, match="make data"):
        agentkit.eval_labels(str(tmp_path / "nope.json"))


def test_eval_labels_from_an_older_version_say_how_to_refresh(tmp_path):
    old = tmp_path / "eval_labels.json"
    old.write_text(json.dumps({"INC1": {"priority": 3, "service": "search"}}))
    with pytest.raises(SystemExit, match="servicedesk.generate --if-missing"):
        agentkit.eval_labels(str(old))
    old.write_text(json.dumps({"INC1": {"priority": 3, "service": "search", "related": ["INC0"]}}))
    assert agentkit.eval_labels(str(old))["INC1"]["related"] == ["INC0"]


def test_save_result_replaces_a_run_of_the_same_name(tmp_path):
    agentkit.save_result("Model alone", {"priority_exact": 0.31, "seconds": 1.2}, data_dir=str(tmp_path))
    agentkit.save_result("With retrieval", {"priority_exact": 0.6}, data_dir=str(tmp_path))
    agentkit.save_result("Model alone", {"priority_exact": 0.35, "seconds": 1.1}, data_dir=str(tmp_path))
    runs = json.loads((tmp_path / "results.json").read_text())["runs"]
    assert [r["name"] for r in runs] == ["Model alone", "With retrieval"]
    assert runs[0]["priority_exact"] == 0.35 and "saved_at" in runs[0]


def test_save_result_survives_a_broken_file(tmp_path):
    (tmp_path / "results.json").write_text("{not json")
    agentkit.save_result("Model alone", {"priority_exact": 0.3}, data_dir=str(tmp_path))
    assert len(json.loads((tmp_path / "results.json").read_text())["runs"]) == 1


def test_load_picks_the_learners_file_or_the_solution(tmp_path, monkeypatch):
    folder = tmp_path / "99-demo"
    (folder / "_solution").mkdir(parents=True)
    (folder / "thing.py").write_text("WHO = 'learner'\n")
    (folder / "_solution" / "thing.py").write_text("WHO = 'solution'\n")
    monkeypatch.delenv("LAB_SOLUTIONS", raising=False)
    assert agentkit.load("99-demo", "thing", lessons_dir=str(tmp_path)).WHO == "learner"
    monkeypatch.setenv("LAB_SOLUTIONS", "1")
    assert agentkit.load("99-demo", "thing", lessons_dir=str(tmp_path)).WHO == "solution"


SPEC = {"type": "function", "function": {"name": "get_service", "description": "Look up one service.",
        "parameters": {"type": "object", "properties": {"service_id": {"type": "string", "description": "The id."}},
                       "required": ["service_id"]}}}


def reply_with(content):
    return lambda m, p, b: (200, {"message": {"role": "assistant", "content": content}, "prompt_eval_count": 50, "eval_count": 12})


def test_step_turns_a_json_action_into_a_standard_tool_call(fake):
    url, seen = fake(reply_with(json.dumps({"thought": "Need the owner.", "tool": "get_service", "arguments": {"service_id": "payments"}})))
    r = agentkit.step([{"role": "system", "content": "Be brief."}, {"role": "user", "content": "Who owns payments?"}],
                      tools=[SPEC], host=url, temperature=0)
    assert r["message"] == {"role": "assistant", "content": "", "thought": "Need the owner.",
                            "tool_calls": [{"function": {"name": "get_service", "arguments": {"service_id": "payments"}}}]}
    body = seen[0][2]
    system = body["messages"][0]["content"]
    assert system.startswith("Be brief.") and "get_service: Look up one service." in system and "final_answer" in system
    assert "tools" not in body and body["think"] is False and body["options"] == {"temperature": 0}
    allowed = [o["properties"]["tool"]["const"] for o in body["format"]["anyOf"]]
    assert allowed == ["get_service", "final_answer"]
    assert body["format"]["anyOf"][0]["properties"]["arguments"] == SPEC["function"]["parameters"]


def test_step_turns_final_answer_into_plain_content(fake):
    url, _ = fake(reply_with(json.dumps({"thought": "Done.", "tool": "final_answer", "arguments": {"answer": "The Payments team."}})))
    r = agentkit.step([{"role": "user", "content": "Who owns payments?"}], tools=[SPEC], host=url)
    assert r["message"] == {"role": "assistant", "content": "The Payments team.", "thought": "Done."}
    assert r["prompt_tokens"] == 50 and r["output_tokens"] == 12


def test_step_replays_earlier_calls_and_results_as_text_the_model_can_read(fake):
    url, seen = fake(reply_with(json.dumps({"thought": "", "tool": "final_answer", "arguments": {"answer": "ok"}})))
    history = [{"role": "user", "content": "Who owns payments?"},
               {"role": "assistant", "content": "", "thought": "Look it up.",
                "tool_calls": [{"function": {"name": "get_service", "arguments": {"service_id": "payments"}}}]},
               {"role": "tool", "tool_name": "get_service", "content": '{"team": "Payments"}'}]
    agentkit.step(history, tools=[SPEC], host=url)
    sent = seen[0][2]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert json.loads(sent[2]["content"]) == {"thought": "Look it up.", "tool": "get_service", "arguments": {"service_id": "payments"}}
    assert sent[3]["content"] == 'Result of get_service: {"team": "Payments"}'


def test_step_treats_an_unusable_reply_as_the_answer(fake):
    url, _ = fake(reply_with('{"thought": "cut off mid'))
    r = agentkit.step([{"role": "user", "content": "x"}], tools=[SPEC], host=url)
    assert r["message"]["content"] == '{"thought": "cut off mid' and "tool_calls" not in r["message"]


def test_commit_returns_the_parsed_answer_and_sends_the_schema(fake):
    url, seen = fake(reply_with('{"priority": 3, "service": "payments"}'))
    schema = {"type": "object", "properties": {"priority": {"type": "integer"}}}
    history = [{"role": "system", "content": "You triage."}, {"role": "user", "content": "New incident"},
               {"role": "assistant", "content": "", "thought": "search",
                "tool_calls": [{"function": {"name": "search_incidents", "arguments": {"query": "refund"}}}]},
               {"role": "tool", "tool_name": "search_incidents", "content": '{"incidents": []}'},
               {"role": "user", "content": "Now commit."}]
    assert agentkit.commit(history, schema, host=url, temperature=0) == {"priority": 3, "service": "payments"}
    body = seen[0][2]
    assert body["format"] == schema and "tools" not in body and body["messages"][0] == {"role": "system", "content": "You triage."}
    assert [m["role"] for m in body["messages"]] == ["system", "user", "assistant", "user", "user"]
    assert body["messages"][3]["content"].startswith("Result of search_incidents:")
    assert agentkit.commit.last["prompt_tokens"] == 50


def test_commit_returns_none_for_an_unusable_reply(fake):
    url, _ = fake(reply_with('{"priority": 3, "serv'))
    assert agentkit.commit([{"role": "user", "content": "x"}], {"type": "object"}, host=url) is None
    url, _ = fake(reply_with("[1, 2]"))
    assert agentkit.commit([{"role": "user", "content": "x"}], {"type": "object"}, host=url) is None
