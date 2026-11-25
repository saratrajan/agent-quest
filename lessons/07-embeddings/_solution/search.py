"""Session 7: similarity search, written by you.

An embedding model turns a text into a list of numbers, a vector, placed so
that texts with similar meaning point in similar directions. Search is then
arithmetic: embed the question, and find the stored vectors that point the
same way. The model is given (you will not train one); the search is yours.

Fill the five gaps marked YOUR CODE (about 25 lines in total).
"""
import math
from collections import Counter

import numpy as np


def cosine_by_hand(a: list[float], b: list[float]) -> float:
    """Cosine similarity of two vectors, in plain Python: the dot product
    divided by the product of the two lengths. 1 means the same direction,
    0 means unrelated, -1 means opposite."""
    # >>> YOUR CODE (about 4 lines)
    dot = sum(x * y for x, y in zip(a, b))
    length_a = math.sqrt(sum(x * x for x in a))
    length_b = math.sqrt(sum(y * y for y in b))
    return dot / (length_a * length_b)
    # <<< YOUR CODE


def normalise(matrix: np.ndarray) -> np.ndarray:
    """Scale every row to length 1, so that a dot product between rows IS
    their cosine. matrix has one vector per row.
    np.linalg.norm(matrix, axis=1, keepdims=True) gives each row's length."""
    # >>> YOUR CODE (1 or 2 lines)
    return matrix / np.linalg.norm(matrix, axis=1, keepdims=True)
    # <<< YOUR CODE


def top_k(query: np.ndarray, matrix: np.ndarray, k: int) -> list[tuple[int, float]]:
    """The k rows of matrix most similar to the query vector, best first, as
    (row index, cosine) pairs. Compare against every row: with a few hundred
    vectors, one matrix product is all it takes.
    np.argsort(scores)[::-1] gives the indices from highest score to lowest."""
    # >>> YOUR CODE (about 4 lines)
    scores = normalise(matrix) @ (query / np.linalg.norm(query))
    order = np.argsort(scores)[::-1][:k]
    return [(int(i), float(scores[i])) for i in order]
    # <<< YOUR CODE


def hit_at_k(retrieved: list[list[str]], relevant: list[set[str]], k: int) -> float:
    """Retrieval quality. For each query you have the ids retrieved (best
    first) and the set of ids that are truly related. Return the fraction of
    queries with at least one truly related id among their first k."""
    # >>> YOUR CODE (about 2 lines)
    hits = sum(bool(set(got[:k]) & want) for got, want in zip(retrieved, relevant))
    return hits / len(retrieved)
    # <<< YOUR CODE


def vote(neighbours: list[dict]) -> dict:
    """Triage with no language model at all: answer with the most common
    priority and the most common service among the retrieved incidents.
    neighbours are incident dicts, nearest first; on a tie the nearest wins,
    which Counter(...).most_common(1) gives you because it keeps first-seen
    order among equals. Returns {"priority", "service"}."""
    # >>> YOUR CODE (about 3 lines)
    priority = Counter(n["priority"] for n in neighbours).most_common(1)[0][0]
    service = Counter(n["service"] for n in neighbours).most_common(1)[0][0]
    return {"priority": priority, "service": service}
    # <<< YOUR CODE
