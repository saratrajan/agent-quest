"""Given: the agent's tools. Six read-only lookups and their descriptions.

They are the session 9 tools with two changes that came out of that
session's experiments: search now uses the hybrid retrieval you built in
session 8 instead of a keyword match, and there is a way to see every
runbook, because the right one is not always filed under the service the
incident is on.
"""
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import agentkit  # noqa: E402

for folder in ("08-rag", "09-tool-calling"):
    sys.path.insert(0, str(HERE.parent / folder))
import desk_tools  # noqa: E402  (session 9)
import store  # noqa: E402       (session 8)

loop = desk_tools.loop
_index = None


def index():
    global _index
    if _index is None:
        _index = store.Index()
    return _index


def search_incidents(query: str) -> dict:
    """The five resolved incidents most similar to a description, by YOUR hybrid search."""
    found = index().get(index().hybrid(query, 5))
    return {"incidents": [{"number": p["number"], "summary": p["short_description"], "final_priority": p["priority"],
                           "service": p["service"], "root_cause": p["root_cause_category"],
                           "resolution": loop.clip(p["resolution"] or "", 220)} for p in found]}


def list_runbooks() -> dict:
    """Every runbook: id, title and the service it is filed under."""
    return {"runbooks": agentkit.desk("/api/runbooks")["result"]}


TOOLS = {"search_incidents": search_incidents, "get_incident": desk_tools.get_incident, "get_service": desk_tools.get_service,
         "list_runbooks": list_runbooks, "get_runbook": desk_tools.get_runbook, "recent_deploys": desk_tools.recent_deploys}


def specs() -> list[dict]:
    given = {s["function"]["name"]: s for s in desk_tools.specs()}
    return [
        loop.tool_spec("search_incidents",
                       "Find the five past, resolved incidents most similar to a description. Each comes with the priority and service "
                       "it ended at, its root cause category and its resolution. Pass the new incident's summary and description.",
                       {"query": "A description of the problem, in a sentence or two."}),
        given["get_incident"], given["get_service"],
        loop.tool_spec("list_runbooks", "List every runbook with its id, title and service. Use it to find the runbook for a likely cause.", {}),
        given["get_runbook"], given["recent_deploys"],
    ]
