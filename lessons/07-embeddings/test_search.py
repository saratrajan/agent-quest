"""Tests for session 7. Run from the course app, or: pytest lessons/07-embeddings -q"""
import os

import numpy as np

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.search import cosine_by_hand, hit_at_k, normalise, top_k, vote
else:
    from search import cosine_by_hand, hit_at_k, normalise, top_k, vote

# The four stored vectors and the query from the lesson's worked example.
STORED = np.array([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0], [-1.0, 0.0]])
QUERY = np.array([2.0, 1.0])


def test_cosine_on_the_lesson_examples():
    assert round(cosine_by_hand([1, 0], [1, 1]), 4) == 0.7071
    assert round(cosine_by_hand([3, 4], [4, 3]), 4) == 0.96
    assert cosine_by_hand([1, 0], [0, 5]) == 0 and round(cosine_by_hand([1, 2], [-1, -2]), 6) == -1


def test_cosine_ignores_length():
    assert abs(cosine_by_hand([1, 2, 3], [2, 4, 6]) - 1) < 1e-9
    assert abs(cosine_by_hand([3, 4], [4, 3]) - cosine_by_hand([30, 40], [0.4, 0.3])) < 1e-9


def test_normalise_gives_rows_of_length_one_and_keeps_direction():
    unit = normalise(np.array([[3.0, 4.0], [0.0, 2.0], [1.0, 1.0]]))
    assert np.allclose(np.linalg.norm(unit, axis=1), 1)
    assert np.allclose(unit[0], [0.6, 0.8]) and np.allclose(unit[1], [0, 1])


def test_top_k_on_the_lesson_example():
    got = top_k(QUERY, STORED, 2)
    assert [i for i, _ in got] == [2, 0]
    assert [round(s, 4) for _, s in got] == [0.9487, 0.8944]


def test_top_k_agrees_with_cosine_by_hand_and_is_sorted():
    rng = np.random.default_rng(3)
    matrix, query = rng.normal(size=(40, 8)), rng.normal(size=8)
    got = top_k(query, matrix, 5)
    assert len(got) == 5 and [s for _, s in got] == sorted((s for _, s in got), reverse=True)
    for i, s in got:
        assert abs(s - cosine_by_hand(query.tolist(), matrix[i].tolist())) < 1e-9
    best = max(range(40), key=lambda i: cosine_by_hand(query.tolist(), matrix[i].tolist()))
    assert got[0][0] == best and isinstance(got[0][0], int) and isinstance(got[0][1], float)


def test_top_k_larger_than_the_store_returns_everything():
    assert [i for i, _ in top_k(QUERY, STORED, 10)] == [2, 0, 1, 3]


def test_hit_at_k_on_the_lesson_example():
    retrieved = [["a", "b", "c"], ["d", "e", "f"], ["g", "h", "i"], ["j", "k", "l"]]
    relevant = [{"a"}, {"f", "z"}, {"x"}, {"k"}]
    assert hit_at_k(retrieved, relevant, 1) == 0.25    # only the first query has a related id at rank 1
    assert hit_at_k(retrieved, relevant, 2) == 0.5     # the fourth finds one at rank 2
    assert hit_at_k(retrieved, relevant, 3) == 0.75    # the second finds one at rank 3; the third never does


def test_vote_takes_the_most_common_and_the_nearest_wins_a_tie():
    near = [{"priority": 2, "service": "payments"}, {"priority": 3, "service": "payments"},
            {"priority": 3, "service": "search"}, {"priority": 3, "service": "identity"}, {"priority": 4, "service": "search"}]
    assert vote(near) == {"priority": 3, "service": "payments"}   # payments and search tie at 2; payments is nearer
    assert vote(near[:1]) == {"priority": 2, "service": "payments"}
