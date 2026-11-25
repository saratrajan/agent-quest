"""Given: the plumbing for sessions 6 to 10. Nothing here needs editing.

It does four dull jobs so the lesson files can stay about the idea:

    desk(path)            read from (or post to) the service desk over HTTP
    ask(prompt)           one prompt to the local model, answered directly as JSON
    chat(messages, tools) one turn of a conversation, optionally with tools
    embed(texts)          text to vectors, with the local embedding model

plus the held-back answers, the results board, and loading your own code
from an earlier session. Read it once: it is short, and it is everything
that goes over the wire.
"""
import importlib.util
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DESK = os.environ.get("DESK_URL", "http://localhost:8080")
OLLAMA = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = "qwen3:4b"
EMBED_MODEL = "nomic-embed-text"


def _json(url: str, body: dict | None = None, timeout: int = 300) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


# ------------------------------------------------------------ service desk
def desk(path: str, body: dict | None = None, host: str | None = None) -> dict:
    """GET a desk path, or POST when a body is given. The agent's only way in."""
    host = host or DESK
    try:
        return _json(host + path, body, timeout=20)
    except urllib.error.HTTPError as err:
        try:
            detail = json.loads(err.read()).get("detail")
        except ValueError:
            detail = None
        raise LookupError(str(detail or f"The service desk answered {err.code} for {path}")) from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Could not reach the service desk at {host}. Start it with: make desk") from None


def history(host: str | None = None) -> list[dict]:
    """Every resolved incident the agent may learn from (the oldest 400), newest first."""
    rows, offset = [], 0
    while True:
        page = desk(f"/api/now/table/incident?limit=100&offset={offset}", host=host)
        rows += page["result"]
        offset += 100
        if offset >= page["total"] or not page["result"]:
            break
    return [r for r in rows if r.get("resolution")]


def eval_incidents(host: str | None = None) -> list[dict]:
    """The 100 held-back incidents, as the desk shows them: no answers."""
    return desk("/api/eval/incidents", host=host)["result"]


def eval_labels(path: str = "data/eval_labels.json") -> dict:
    """The answers for the held-back incidents. Only scoring code should read this."""
    p = Path(path)
    if not p.exists():
        sys.exit(f"{path} is missing. Run `make data` first, from the project folder.")
    labels = json.loads(p.read_text())
    if labels and "related" not in next(iter(labels.values())):
        sys.exit(f"{path} is from an older version. Refresh it with: python -m servicedesk.generate --if-missing")
    return labels


# ------------------------------------------------------------ local model
def _ollama(path: str, body: dict, host: str | None, timeout: int) -> tuple[dict, float]:
    host = host or OLLAMA
    started = time.perf_counter()
    try:
        data = _json(host + path, body, timeout)
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:200]
        if err.code == 404:
            raise RuntimeError(f"Ollama does not have the model '{body['model']}'. Fetch it with: ollama pull {body['model']}") from None
        raise RuntimeError(f"Ollama answered with an error ({err.code}): {detail}") from None
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Could not reach Ollama at {host}. Open the Ollama app, or run: ollama serve") from None
    return data, round(time.perf_counter() - started, 2)


def ask(prompt: str, model: str = MODEL, host: str | None = None, schema: dict | None = None,
        timeout: int = 300, **options) -> dict:
    """One prompt, one direct JSON answer (no thinking: session 5 showed what that costs).

    schema, if given, is a JSON Schema the answer must follow; otherwise any JSON object.
    Extra keywords are sampling options: temperature, num_ctx, num_predict, seed.
    Returns text, prompt_tokens, output_tokens and wall-clock seconds.
    """
    body = {"model": model, "prompt": prompt, "stream": False, "think": False,
            "format": schema or "json", "options": options}
    data, seconds = _ollama("/api/generate", body, host, timeout)
    return {"text": (data.get("response") or "").strip(), "prompt_tokens": data.get("prompt_eval_count", 0),
            "output_tokens": data.get("eval_count", 0), "seconds": seconds}


def chat(messages: list[dict], tools: list[dict] | None = None, model: str = MODEL, host: str | None = None,
         schema: dict | None = None, think: bool = False, timeout: int = 300, **options) -> dict:
    """One turn of a conversation. With tools, the reply may carry tool_calls instead of text.
    think=True lets the model reason first; its reasoning comes back as message["thinking"].

    Returns the assistant's message as Ollama sent it (role, content, maybe
    tool_calls), plus token counts and seconds.
    """
    body = {"model": model, "messages": messages, "stream": False, "think": think, "options": options}
    if tools:
        body["tools"] = tools
    if schema:
        body["format"] = schema
    data, seconds = _ollama("/api/chat", body, host, timeout)
    return {"message": data.get("message") or {"role": "assistant", "content": ""},
            "prompt_tokens": data.get("prompt_eval_count", 0), "output_tokens": data.get("eval_count", 0),
            "seconds": seconds}


def embed(texts: list[str], model: str = EMBED_MODEL, host: str | None = None, batch: int = 64,
          timeout: int = 300) -> list[list[float]]:
    """Turn each text into a vector. Same order out as in."""
    vectors: list[list[float]] = []
    for i in range(0, len(texts), batch):
        data, _ = _ollama("/api/embed", {"model": model, "input": texts[i:i + batch]}, host, timeout)
        vectors += data["embeddings"]
    return vectors


# ------------------------------------------------------------ results board
def save_result(name: str, record: dict, data_dir: str = "data") -> None:
    """Add or replace one row on the course app's results board (data/results.json)."""
    path = Path(data_dir) / "results.json"
    try:
        runs = json.loads(path.read_text())["runs"]
    except (OSError, ValueError, KeyError, TypeError):
        runs = []
    row = {**record, "name": name, "saved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if any(r.get("name") == name for r in runs):
        runs = [row if r.get("name") == name else r for r in runs]
    else:
        runs.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"runs": runs}, indent=1))


# ------------------------------------------------------------ your own code
def load(folder: str, module: str, lessons_dir: str | None = None):
    """Import a file you wrote in an earlier session, for example load("06-baseline", "scoring").

    With LAB_SOLUTIONS=1 in the environment the reference solution is loaded
    instead, which is how the course's own checks run.
    """
    base = Path(lessons_dir) if lessons_dir else Path(__file__).parent
    sub = "_solution" if os.environ.get("LAB_SOLUTIONS") == "1" else ""
    path = base / folder / sub / f"{module}.py"
    spec = importlib.util.spec_from_file_location(f"lab_{folder.replace('-', '_')}_{module}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ------------------------------------------------------------ tool calling, the fast way
STEP_RULES = ('Reply with one JSON object: {"thought": "<one or two sentences: what you know so far and what you need next>", '
              '"tool": "<name>", "arguments": {...}}. One tool per reply. Never repeat a call you have already made; '
              "if a call failed, read the error and change the arguments.")


def _step_prompt(tools: list[dict]) -> tuple[str, dict]:
    """The tool list as text for the model, and a schema that only allows a valid call or a final answer."""
    lines, options = [], []
    for spec in tools:
        f = spec["function"]
        args = "; ".join(f"{name} = {p.get('description', '')}" for name, p in f["parameters"]["properties"].items())
        lines.append(f"- {f['name']}: {f['description']}\n    arguments: {args or 'none'}")
        options.append({"type": "object", "required": ["thought", "tool", "arguments"],
                        "properties": {"thought": {"type": "string"}, "tool": {"const": f["name"]}, "arguments": f["parameters"]}})
    lines.append("- final_answer: give your answer once you have what you need.\n    arguments: answer = your reply")
    options.append({"type": "object", "required": ["thought", "tool", "arguments"],
                    "properties": {"thought": {"type": "string"}, "tool": {"const": "final_answer"},
                                   "arguments": {"type": "object", "properties": {"answer": {"type": "string"}}, "required": ["answer"]}}})
    return "Tools:\n" + "\n".join(lines) + "\n\n" + STEP_RULES, {"anyOf": options}


def _as_text(messages: list[dict], listing: str = "") -> tuple[str, list[dict]]:
    """Tool calls and tool results rewritten as plain messages, plus the system text."""
    sent, system = [], listing
    for m in messages:
        if m["role"] == "system":
            system = (m["content"] + "\n\n" + listing).strip()
        elif m["role"] == "tool":
            sent.append({"role": "user", "content": f"Result of {m.get('tool_name', 'the tool')}: {m['content']}"})
        elif m.get("tool_calls"):
            f = m["tool_calls"][0]["function"]
            sent.append({"role": "assistant", "content": json.dumps(
                {"thought": m.get("thought", ""), "tool": f["name"], "arguments": f.get("arguments") or {}})})
        elif m["role"] == "assistant":
            sent.append({"role": "assistant", "content": json.dumps(
                {"thought": m.get("thought", ""), "tool": "final_answer", "arguments": {"answer": m.get("content", "")}})})
        else:
            sent.append(m)
    return system, sent


def commit(messages: list[dict], schema: dict, model: str = MODEL, host: str | None = None,
           timeout: int = 300, **options) -> dict | None:
    """One last model turn whose reply must follow the given JSON Schema.

    Takes a conversation that step() and your tool loop produced, and returns
    the parsed answer as a dict, or None if the reply was not usable JSON.
    The token counts and seconds of the call are left in commit.last.
    """
    system, sent = _as_text(messages)
    reply = chat([{"role": "system", "content": system}] + sent, model=model, host=host, schema=schema, timeout=timeout, **options)
    commit.last = reply
    try:
        answer = json.loads(reply["message"].get("content", ""))
    except ValueError:
        return None
    return answer if isinstance(answer, dict) else None


commit.last = {}


def step(messages: list[dict], tools: list[dict] | None = None, model: str = MODEL, host: str | None = None,
         timeout: int = 300, **options) -> dict:
    """One model turn with tools, in the same shape as chat(), but fast.

    chat() uses the model's built-in tool calling, which on this model always
    reasons at length first (tens of seconds a turn). step() does by hand what
    the runtime does for you: it writes the tool descriptions into the system
    message, constrains the reply to one JSON object holding a short thought
    and one action, and converts that back into the usual message shape:

        {"role": "assistant", "content": "", "thought": "...", "tool_calls": [{"function": {...}}]}
        {"role": "assistant", "content": "<the answer>", "thought": "..."}       when it is done

    Earlier tool calls and results in messages are converted the same way,
    so your loop does not need to know which of the two is in use.
    """
    listing, schema = _step_prompt(tools or [])
    system, sent = _as_text(messages, listing)
    reply = chat([{"role": "system", "content": system}] + sent, model=model, host=host, schema=schema, timeout=timeout, **options)
    raw = reply["message"].get("content", "")
    try:
        action = json.loads(raw)
        name, arguments, thought = action["tool"], action.get("arguments") or {}, action.get("thought", "")
    except (ValueError, KeyError, TypeError):
        message = {"role": "assistant", "content": raw, "thought": ""}  # not a usable action: treat the text as the answer
    else:
        if name == "final_answer":
            message = {"role": "assistant", "content": str(arguments.get("answer", "")), "thought": thought}
        else:
            message = {"role": "assistant", "content": "", "thought": thought,
                       "tool_calls": [{"function": {"name": name, "arguments": arguments}}]}
    return {**reply, "message": message}
