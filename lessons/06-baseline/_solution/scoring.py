"""Session 6: measuring triage, written by you.

Before building anything clever you need a number that says how good triage
is, and a floor that says how good it is with no cleverness at all. This
file is that measuring kit. Everything from here to session 14 is judged
with it.

    predictions   {"INC0010401": {"priority": 3, "service": "payments"}, "INC0010402": None, ...}
                  None means the model's reply could not be used.
    labels        {"INC0010401": {"priority": 4, "service": "payments", ...}, ...}

Fill the five gaps marked YOUR CODE (about 40 lines in total).
"""
import json
from collections import Counter


def build_prompt(incident: dict, services: list[str]) -> str:
    """The whole request to the model, for one incident, with no help: no past
    incidents, no runbooks. Include the incident's short_description and
    description, the list of service ids to choose from, what the priorities
    1 to 4 are (1 is the most severe), and ask for JSON with exactly the keys
    "priority" (a number) and "service" (one id from the list)."""
    # >>> YOUR CODE (about 8 lines)
    return (
        "You are triaging an incident for Time Travel Inc., a travel booking company.\n"
        f"Summary: {incident['short_description']}\n"
        f"Description: {incident['description']}\n\n"
        "Choose a priority from 1 (critical) to 4 (low), and the affected service from this list: "
        f"{', '.join(services)}.\n"
        'Answer as JSON: {"priority": <number>, "service": "<id from the list>"}'
    )
    # <<< YOUR CODE


def parse_triage(text: str) -> dict | None:
    """Turn the model's reply into {"priority": int, "service": str}, or None
    if it cannot be used. Never raise: a model can return anything.

    Usable means: valid JSON, an object, a priority that is 1 to 4 (accept
    the number 2, the string "2" and the string "P2"), and a service that is
    a non-empty string (strip spaces, lower-case it).
    """
    # >>> YOUR CODE (about 10 lines)
    try:
        data = json.loads(text)
        priority = int(str(data["priority"]).strip().upper().removeprefix("P"))
        service = data["service"].strip().lower()
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if priority not in (1, 2, 3, 4) or not service:
        return None
    return {"priority": priority, "service": service}
    # <<< YOUR CODE


def score(predictions: dict, labels: dict) -> dict:
    """Fractions over ALL the labelled incidents; an unusable or missing
    prediction counts as wrong everywhere.

    Returns {"n", "answered", "priority_exact", "priority_within_one", "service"}:
    n and answered are counts, the other three are fractions from 0 to 1.
    """
    # >>> YOUR CODE (about 10 lines)
    n = len(labels)
    answered = exact = near = service = 0
    for number, truth in labels.items():
        guess = predictions.get(number)
        if guess is None:
            continue
        answered += 1
        exact += guess["priority"] == truth["priority"]
        near += abs(guess["priority"] - truth["priority"]) <= 1
        service += guess["service"] == truth["service"]
    return {"n": n, "answered": answered, "priority_exact": exact / n,
            "priority_within_one": near / n, "service": service / n}
    # <<< YOUR CODE


def confusion(predictions: dict, labels: dict) -> list[list[int]]:
    """A 4 x 4 table of counts: row = the true priority, column = the
    predicted one, both in the order P1, P2, P3, P4. So table[2][0] counts
    incidents that were really P3 and were called P1. Skip unusable predictions."""
    # >>> YOUR CODE (about 5 lines)
    table = [[0] * 4 for _ in range(4)]
    for number, truth in labels.items():
        if predictions.get(number):
            table[truth["priority"] - 1][predictions[number]["priority"] - 1] += 1
    return table
    # <<< YOUR CODE


def majority_baseline(labels: dict) -> dict:
    """The laziest possible triager: always answer with the most common
    priority and the most common service. Returns {"priority", "service"}.
    Counter(...).most_common(1) gives [(value, count)]."""
    # >>> YOUR CODE (about 3 lines)
    priority = Counter(l["priority"] for l in labels.values()).most_common(1)[0][0]
    service = Counter(l["service"] for l in labels.values()).most_common(1)[0][0]
    return {"priority": priority, "service": service}
    # <<< YOUR CODE
