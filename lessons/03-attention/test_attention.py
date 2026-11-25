"""Tests for session 3. Run from the course app, or: pytest lessons/03-attention -q"""
import math
import os

import torch

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.attention import Head, attention_by_hand, causal_mask, scaled_dot_product
else:
    from attention import Head, attention_by_hand, causal_mask, scaled_dot_product

KEYS = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
VALUES = [[1.0, 0.0], [0.0, 1.0], [2.0, 2.0]]


def test_attention_by_hand_on_the_lesson_example():
    weights, out = attention_by_hand([1.0, 1.0], KEYS, VALUES)
    assert [round(w, 4) for w in weights] == [0.2483, 0.2483, 0.5035]
    assert all(abs(o - 1.2552) < 1e-3 for o in out) and len(out) == 2


def test_attention_by_hand_weights_always_sum_to_one():
    weights, _ = attention_by_hand([0.3, -2.0], KEYS, VALUES)
    assert abs(sum(weights) - 1.0) < 1e-9 and weights[0] > weights[2] > weights[1]


def test_causal_mask_lets_each_position_see_itself_and_the_past():
    assert causal_mask(3).tolist() == [[True, False, False], [True, True, False], [True, True, True]]
    assert causal_mask(1).tolist() == [[True]]


def test_scaled_dot_product_matches_the_hand_example():
    q = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    out, w = scaled_dot_product(q, torch.tensor(KEYS), torch.tensor(VALUES))
    assert torch.allclose(w[2], torch.tensor([0.2483, 0.2483, 0.5035]), atol=1e-4)
    assert torch.allclose(out[2], torch.tensor([1.2552, 1.2552]), atol=1e-3)
    assert torch.allclose(w.sum(-1), torch.ones(3))


def test_mask_removes_the_future_exactly():
    q = torch.tensor([[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    _, w = scaled_dot_product(q, torch.tensor(KEYS), torch.tensor(VALUES), mask=causal_mask(3))
    assert w[0].tolist() == [1.0, 0.0, 0.0]
    assert torch.allclose(w[1], torch.tensor([0.3302, 0.6698, 0.0]), atol=1e-4)
    assert torch.equal(w.triu(1), torch.zeros(3, 3)) and torch.allclose(w.sum(-1), torch.ones(3))


def test_scaled_dot_product_handles_batches():
    torch.manual_seed(0)
    x = torch.randn(4, 6, 8)
    out, w = scaled_dot_product(x, x, x, mask=causal_mask(6))
    assert out.shape == (4, 6, 8) and w.shape == (4, 6, 6)


def test_head_output_shape():
    torch.manual_seed(0)
    head = Head(n_embd=8, head_size=4, block_size=6)
    assert head(torch.randn(2, 6, 8)).shape == (2, 6, 4)
    assert head(torch.randn(2, 3, 8)).shape == (2, 3, 4)  # shorter than the block is fine


def test_head_cannot_see_the_future():
    torch.manual_seed(0)
    head = Head(n_embd=8, head_size=4, block_size=6)
    x = torch.randn(1, 6, 8)
    changed = x.clone()
    changed[0, 5] += 10.0  # alter only the last token
    a, b = head(x), head(changed)
    assert torch.allclose(a[0, :5], b[0, :5], atol=1e-6) and not torch.allclose(a[0, 5], b[0, 5])
