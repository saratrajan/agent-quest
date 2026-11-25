"""Given: five read-only tools over the service desk, and their descriptions.

Each tool is an ordinary Python function that makes one HTTP request and
returns a small dict. Nothing here needs editing, but read the descriptions:
they are the only thing the model knows about each tool, and writing them
well is half of making tool calling work.
"""
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import agentkit  # noqa: E402

loop = agentkit.load("09-tool-calling", "loop")


def search_incidents(query: str) -> dict:
    """Resolved incidents whose summary or description contains the words given."""
    found = agentkit.desk("/api/now/table/incident?limit=5&q=" + urllib.parse.quote(query))
    return {"total_matching": found["total"],
            "incidents": [{k: r.get(k) for k in ("number", "short_description", "priority", "service", "opened_at")}
                          for r in found["result"] if r.get("resolution")]}


def get_incident(number: str) -> dict:
    """One incident in full. A resolved one includes its final priority, service and resolution."""
    r = agentkit.desk(f"/api/now/table/incident/{urllib.parse.quote(number)}")["result"]
    notes = r.pop("work_notes", [])
    r["work_notes"] = [f"{n['author']} ({n['role']}): {n['text']}" for n in notes[-4:]]
    return r


def get_service(service_id: str) -> dict:
    """One service: its owning team, its tier (1 is the most critical) and what it depends on."""
    s = agentkit.desk(f"/api/services/{urllib.parse.quote(service_id)}")["result"]
    s["runbooks"] = agentkit.desk(f"/api/runbooks?service={urllib.parse.quote(service_id)}")["result"]
    return s


def get_runbook(runbook_id: str) -> dict:
    """The steps of one runbook."""
    return agentkit.desk(f"/api/runbooks/{urllib.parse.quote(runbook_id)}")["result"]


def recent_deploys(service_id: str, before: str) -> dict:
    """Deploys to one service in the 24 hours before a moment in time."""
    q = urllib.parse.urlencode({"service": service_id, "before": before, "hours": 24})
    return agentkit.desk(f"/api/deploys?{q}")


TOOLS = {"search_incidents": search_incidents, "get_incident": get_incident, "get_service": get_service,
         "get_runbook": get_runbook, "recent_deploys": recent_deploys}

SERVICE_IDS = ("search, flight-booking, hotel-booking, cruises, payments, identity, notifications, pricing, "
               "supplier-sync, web-frontend, mobile-gateway, loyalty")


def specs() -> list[dict]:
    """The descriptions sent to the model, built with YOUR tool_spec."""
    return [
        loop.tool_spec("search_incidents",
                       "Search past, resolved incidents by keyword. Returns up to five with number, summary, final priority and service. "
                       "Use one or two distinctive words, for example 'refund' or 'seat map'; long phrases match nothing.",
                       {"query": "One or two keywords to look for in the summary and description."}),
        loop.tool_spec("get_incident",
                       "Fetch one incident by its number. For a resolved incident this includes the resolution and the last work notes.",
                       {"number": "The incident number, for example INC0010011."}),
        loop.tool_spec("get_service",
                       "Look up one service: owning team, tier (1 is most critical), the services it depends on, and its runbooks.",
                       {"service_id": f"One of: {SERVICE_IDS}."}),
        loop.tool_spec("get_runbook", "Fetch the steps of one runbook. Get runbook ids from get_service.",
                       {"runbook_id": "The runbook id, for example rb-cert-renewal."}),
        loop.tool_spec("recent_deploys",
                       "List deploys to one service in the 24 hours before a given time. Use it to check whether a release lines up with the start of a problem.",
                       {"service_id": f"One of: {SERVICE_IDS}.",
                        "before": "A UTC timestamp like 2026-07-26T00:58:41Z, normally when the incident was opened."}),
    ]
