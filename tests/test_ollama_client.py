"""The lesson's Ollama client, tested against a stand-in server so no model is needed."""
import json
import sys
import threading
import socketserver
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("lessons/05-toy-to-real").resolve()))
import ollama_client  # noqa: E402


@pytest.fixture
def server():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if seen["body"]["model"] == "missing":
                self.send_response(404); self.end_headers(); self.wfile.write(b'{"error":"model not found"}')
                return
            reply = {"response": " ready \n", "thinking": "the user wants one word", "prompt_eval_count": 17,
                     "eval_count": 50, "eval_duration": 500_000_000}
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps(reply).encode())

        def log_message(self, *a):
            pass

    httpd = socketserver.TCPServer(("127.0.0.1", 0), Handler)  # plain TCP server: no slow hostname lookup
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", seen
    httpd.shutdown()


def test_generate_returns_text_counts_and_speed(server):
    host, seen = server
    r = ollama_client.generate("hi", host=host, temperature=0.2, num_ctx=512)
    assert r == {"text": "ready", "thinking": "the user wants one word", "prompt_tokens": 17, "output_tokens": 50,
                 "seconds": 0.5, "tokens_per_second": 100.0}
    assert seen["body"]["options"] == {"temperature": 0.2, "num_ctx": 512} and seen["body"]["stream"] is False
    assert "format" not in seen["body"] and seen["body"]["think"] is True


def test_json_output_is_requested_when_asked(server):
    host, seen = server
    ollama_client.generate("hi", host=host, json_output=True, think=False)
    assert seen["body"]["format"] == "json" and seen["body"]["think"] is False


def test_missing_model_says_how_to_fetch_it(server):
    with pytest.raises(RuntimeError, match="ollama pull missing"):
        ollama_client.generate("hi", model="missing", host=server[0])


def test_unreachable_server_says_how_to_start_it():
    with pytest.raises(RuntimeError, match="ollama serve"):
        ollama_client.generate("hi", host="http://127.0.0.1:9", timeout=2)
