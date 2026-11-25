"""Tests for session 5. Run from the course app, or: pytest lessons/05-toy-to-real -q"""
import math
import os

import torch
import torch.nn.functional as F

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.sampling import apply_temperature, sample_next, top_k_filter, top_p_filter
else:
    from sampling import apply_temperature, sample_next, top_k_filter, top_p_filter

PROBS = torch.tensor([0.5, 0.3, 0.15, 0.05])
LOGITS = PROBS.log()


def kept(logits):
    return [i for i, v in enumerate(logits.tolist()) if v != float("-inf")]


def test_temperature_on_the_lesson_example():
    probs = F.softmax(apply_temperature(torch.tensor([2.0, 1.0, 0.0]), 0.5), dim=-1)
    assert [round(p, 4) for p in probs.tolist()] == [0.8668, 0.1173, 0.0159]


def test_temperature_above_one_flattens_and_below_one_sharpens():
    top = lambda t: F.softmax(apply_temperature(LOGITS, t), dim=-1)[0].item()
    assert top(2.0) < 0.5 < top(0.5) and abs(top(1.0) - 0.5) < 1e-6


def test_top_k_keeps_the_k_most_likely():
    assert kept(top_k_filter(LOGITS, 2)) == [0, 1] and kept(top_k_filter(LOGITS, 1)) == [0]
    assert kept(top_k_filter(LOGITS, 10)) == [0, 1, 2, 3]  # k larger than the vocabulary changes nothing
    shuffled = torch.tensor([0.05, 0.5, 0.15, 0.3]).log()
    assert kept(top_k_filter(shuffled, 2)) == [1, 3]


def test_top_p_keeps_the_smallest_set_that_reaches_p():
    assert kept(top_p_filter(LOGITS, 0.75)) == [0, 1]       # 0.5 + 0.3 reaches 0.75
    assert kept(top_p_filter(LOGITS, 0.85)) == [0, 1, 2]    # needs the third to reach 0.85
    assert kept(top_p_filter(LOGITS, 0.4)) == [0]           # the first alone is enough
    assert kept(top_p_filter(LOGITS, 1.0)) == [0, 1, 2, 3]


def test_top_p_works_whatever_order_the_tokens_are_in():
    shuffled = torch.tensor([0.05, 0.5, 0.15, 0.3]).log()
    assert kept(top_p_filter(shuffled, 0.75)) == [1, 3]


def test_temperature_zero_means_take_the_most_likely():
    g = torch.Generator().manual_seed(0)
    assert all(sample_next(LOGITS, temperature=0, generator=g) == 0 for _ in range(20))


def test_top_k_one_always_returns_the_top_token():
    g = torch.Generator().manual_seed(0)
    assert all(sample_next(LOGITS, temperature=1.5, top_k=1, generator=g) == 0 for _ in range(50))


def test_sample_next_never_returns_a_filtered_token():
    g = torch.Generator().manual_seed(0)
    draws = {sample_next(LOGITS, temperature=1.0, top_p=0.75, generator=g) for _ in range(300)}
    assert draws == {0, 1}


def test_sampling_follows_the_distribution():
    g = torch.Generator().manual_seed(0)
    n = 2000
    counts = [0, 0, 0, 0]
    for _ in range(n):
        token = sample_next(LOGITS, temperature=1.0, generator=g)
        assert isinstance(token, int)
        counts[token] += 1
    assert all(abs(c / n - p) < 0.03 for c, p in zip(counts, PROBS.tolist()))
