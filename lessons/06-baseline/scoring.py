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
    raise NotImplementedError("build_prompt is yours to write")
    # <<< YOUR CODE


def parse_triage(text: str) -> dict | None:
    """Turn the model's reply into {"priority": int, "service": str}, or None
    if it cannot be used. Never raise: a model can return anything.

    Usable means: valid JSON, an object, a priority that is 1 to 4 (accept
    the number 2, the string "2" and the string "P2"), and a service that is
    a non-empty string (strip spaces, lower-case it).
    """
    # >>> YOUR CODE (about 10 lines)
    raise NotImplementedError("parse_triage is yours to write")
    # <<< YOUR CODE


def score(predictions: dict, labels: dict) -> dict:
    """Fractions over ALL the labelled incidents; an unusable or missing
    prediction counts as wrong everywhere.

    Returns {"n", "answered", "priority_exact", "priority_within_one", "service"}:
    n and answered are counts, the other three are fractions from 0 to 1.
    """
    # >>> YOUR CODE (about 10 lines)
    raise NotImplementedError("score is yours to write")
    # <<< YOUR CODE


def confusion(predictions: dict, labels: dict) -> list[list[int]]:
    """A 4 x 4 table of counts: row = the true priority, column = the
    predicted one, both in the order P1, P2, P3, P4. So table[2][0] counts
    incidents that were really P3 and were called P1. Skip unusable predictions."""
    # >>> YOUR CODE (about 5 lines)
    raise NotImplementedError("confusion is yours to write")
    # <<< YOUR CODE


def majority_baseline(labels: dict) -> dict:
    """The laziest possible triager: always answer with the most common
    priority and the most common service. Returns {"priority", "service"}.
    Counter(...).most_common(1) gives [(value, count)]."""
    # >>> YOUR CODE (about 3 lines)
    raise NotImplementedError("majority_baseline is yours to write")
    # <<< YOUR CODE
