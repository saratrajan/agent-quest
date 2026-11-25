"""Tests for session 2. Run from the course app, or: pytest lessons/02-next-token -q"""
import math
import os

import torch
import torch.nn.functional as F

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.bigram import BigramModel, cross_entropy_by_hand, get_batch, train_step
else:
    from bigram import BigramModel, cross_entropy_by_hand, get_batch, train_step


def test_cross_entropy_by_hand_on_the_lesson_example():
    assert abs(cross_entropy_by_hand([2.0, 1.0, 0.1], 0) - 0.4170) < 1e-4
    assert abs(cross_entropy_by_hand([2.0, 1.0, 0.1], 2) - 2.3170) < 1e-4


def test_cross_entropy_by_hand_matches_pytorch_and_survives_large_scores():
    logits = [3.2, -1.0, 0.5, 2.2]
    expected = F.cross_entropy(torch.tensor([logits]), torch.tensor([3])).item()
    assert abs(cross_entropy_by_hand(logits, 3) - expected) < 1e-5
    assert abs(cross_entropy_by_hand([1000.0, 999.0], 0) - 0.3133) < 1e-4  # no overflow


def test_get_batch_targets_are_inputs_shifted_by_one():
    g = torch.Generator().manual_seed(0)
    x, y = get_batch(torch.arange(20), block_size=4, batch_size=3, generator=g)
    assert x.shape == (3, 4) and y.shape == (3, 4)
    assert torch.equal(y, x + 1)
    assert int(x.max()) <= 18  # never runs off the end of the data


def test_forward_shapes_and_no_loss_without_targets():
    torch.manual_seed(0)
    model = BigramModel(65)
    idx = torch.randint(65, (4, 8))
    logits, loss = model(idx)
    assert logits.shape == (4, 8, 65) and loss is None


def test_untrained_loss_is_close_to_a_uniform_guess():
    torch.manual_seed(0)
    model = BigramModel(65)
    idx, targets = torch.randint(65, (32, 8)), torch.randint(65, (32, 8))
    _, loss = model(idx, targets)
    assert math.log(65) - 0.1 < loss.item() < math.log(65) + 1.0


def test_training_learns_a_simple_pattern():
    torch.manual_seed(0)
    data = torch.tensor([0, 1] * 200)
    model = BigramModel(2)
    opt = torch.optim.AdamW(model.parameters(), lr=0.1)
    g = torch.Generator().manual_seed(0)
    first = last = None
    for step in range(300):
        loss = train_step(model, opt, *get_batch(data, 8, 16, g))
        first = loss if first is None else first
        last = loss
    assert isinstance(last, float) and last < 0.2 and last < first


def test_generate_continues_the_pattern_after_training():
    torch.manual_seed(0)
    data = torch.tensor([0, 1] * 200)
    model = BigramModel(2)
    opt = torch.optim.AdamW(model.parameters(), lr=0.1)
    g = torch.Generator().manual_seed(0)
    for _ in range(300):
        train_step(model, opt, *get_batch(data, 8, 16, g))
    out = model.generate(torch.tensor([[0]]), 6, generator=g)
    assert out.tolist() == [[0, 1, 0, 1, 0, 1, 0]]
