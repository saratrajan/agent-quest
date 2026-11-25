"""Session 10: the triage agent, written by you.

Everything is already built: scoring (session 6), retrieval (7 and 8) and
the tool loop (9). An agent is those parts arranged around one decision:
let the model investigate with tools for a bounded number of steps, then
make it commit to an answer in a fixed shape, and keep a record of every
step so that a person can see why it said what it said.

Fill the four gaps marked YOUR CODE (about 40 lines in total).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(next(p for p in Path(__file__).resolve().parents if (p / "agentkit.py").exists())))
import agentkit  # noqa: E402

loop = agentkit.load("09-tool-calling", "loop")   # your tool_loop from session 9

CONFIDENCE = ["high", "medium", "low", "not enough information"]
SYSTEM = (
    "You are the first-line triage agent for the on-call team at Time Travel Inc., a travel booking company. "
    "For each new incident, investigate with the tools before deciding. Always search for similar past incidents first "
    "and note the priority and service they ended at. Check for a recent deploy when the description suggests a release. "
    "Look up a runbook when you know the likely cause. "
    "Priority runs from 1 (most severe) to 4. Start from the priority that most of the similar past incidents ended at, "
    "and move away from it only if this ticket clearly describes a wider or narrower impact than they had. "
    "Use at most five tool calls, then give a short summary of what you found."
)
COMMIT = ("Now commit to a triage for this incident as JSON. Use only incident numbers that appeared in the tool "
          "results above. If the evidence is thin, say so in the confidence field instead of guessing.")


def answer_schema(services: list[str]) -> dict:
    """The JSON Schema the final answer must follow. An object with exactly
    these properties, all of them required, in this order:

        priority            {"type": "integer", "enum": [1, 2, 3, 4]}
        service             {"type": "string", "enum": <the service ids given>}
        similar_incidents   {"type": "array", "items": {"type": "string"}, "maxItems": 3}
        probable_cause      {"type": "string"}
        first_steps         {"type": "array", "items": {"type": "string"}, "maxItems": 4}
        confidence          {"type": "string", "enum": CONFIDENCE}

    The enums are what make the answer checkable: the model cannot return a
    priority of 7 or a service that does not exist.
    """
    # >>> YOUR CODE (about 9 lines)
    properties = {
        "priority": {"type": "integer", "enum": [1, 2, 3, 4]},
        "service": {"type": "string", "enum": list(services)},
        "similar_incidents": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
        "probable_cause": {"type": "string"},
        "first_steps": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
        "confidence": {"type": "string", "enum": CONFIDENCE},
    }
    return {"type": "object", "properties": properties, "required": list(properties)}
    # <<< YOUR CODE


def traced(tools: dict, trace: list) -> dict:
    """Wrap every tool so that each call leaves a record.

    Return a new dict with the same names. Calling a wrapped tool calls the
    original with the same keyword arguments and appends one entry to trace:

        {"tool": name, "arguments": {...}, "seconds": <float>, "result": <what it returned>}

    If the original raises, append the entry with "error": str(the exception)
    in place of "result", then re-raise so the loop can report it to the model.
    time.perf_counter() gives a clock for measuring the seconds.
    Careful: define the wrapper in a helper function that takes name and fn,
    or every wrapper will end up calling the last tool in the dict.
    """
    # >>> YOUR CODE (about 13 lines)
    def wrap(name, fn):
        def wrapped(**arguments):
            started = time.perf_counter()
            entry = {"tool": name, "arguments": arguments}
            try:
                entry["result"] = fn(**arguments)
                return entry["result"]
            except Exception as err:
                entry["error"] = str(err)
                raise
            finally:
                entry["seconds"] = round(time.perf_counter() - started, 3)
                trace.append(entry)
        return wrapped

    return {name: wrap(name, fn) for name, fn in tools.items()}
    # <<< YOUR CODE


def check_answer(answer: dict | None, services: list[str], seen_numbers: set[str]) -> list[str]:
    """Problems with a final answer, as a list of short sentences; an empty
    list means it passed. Check, in this order:

      - answer is None                          -> ["no answer"] and nothing else
      - priority is not one of 1, 2, 3, 4       -> "priority out of range"
      - service is not in services              -> "unknown service"
      - a similar incident that is not in seen_numbers
                                                -> "invented incident <number>" (one per number)

    seen_numbers holds every incident number that appeared in a tool result.
    A number the model cites that no tool ever returned was made up.
    """
    # >>> YOUR CODE (about 9 lines)
    if answer is None:
        return ["no answer"]
    problems = []
    if answer.get("priority") not in (1, 2, 3, 4):
        problems.append("priority out of range")
    if answer.get("service") not in services:
        problems.append("unknown service")
    for number in answer.get("similar_incidents") or []:
        if number not in seen_numbers:
            problems.append(f"invented incident {number}")
    return problems
    # <<< YOUR CODE


def triage(incident: dict, tools: dict, specs: list[dict], services: list[str], step, commit, max_steps: int = 6) -> dict:
    """Triage one incident: investigate, then commit.

    step(messages, tools=specs)   one model turn that may call tools (agentkit.step)
    commit(messages, schema)      one model turn whose reply must follow the schema;
                                  returns the parsed answer as a dict, or None

    1. Start a trace (an empty list) and wrap the tools with traced().
    2. Start the conversation: a system message holding SYSTEM, and a user
       message holding the incident's number, opened_at, source,
       priority_at_open, short_description and description.
    3. Run loop.tool_loop with the wrapped tools, the specs, step and max_steps.
    4. Append a user message holding COMMIT, and call commit with the
       messages and answer_schema(services).
    5. Return {"answer": <the dict or None>, "trace": trace, "messages": messages,
               "finished": <False if the loop returned None, else True>}.
    Commit even when the loop ran out of steps: a best answer marked by
    "finished": False is more useful to the caller than nothing.
    """
    # >>> YOUR CODE (about 10 lines)
    trace: list = []
    wrapped = traced(tools, trace)
    ticket = "\n".join(f"{key}: {incident.get(key)}" for key in
                       ("number", "opened_at", "source", "priority_at_open", "short_description", "description"))
    messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": "New incident:\n" + ticket}]
    summary = loop.tool_loop(messages, wrapped, specs, step, max_steps)
    messages.append({"role": "user", "content": COMMIT})
    answer = commit(messages, answer_schema(services))
    return {"answer": answer, "trace": trace, "messages": messages, "finished": summary is not None}
    # <<< YOUR CODE
