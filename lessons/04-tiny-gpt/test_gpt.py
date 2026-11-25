"""Tests for session 4. Run from the course app, or: pytest lessons/04-tiny-gpt -q"""
import os

import pytest
import torch
from parts import Config, get_batch

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.gpt import GPT, Block, MultiHead, estimate_loss
else:
    from gpt import GPT, Block, MultiHead, estimate_loss

SMALL = Config(vocab_size=65, block_size=16, n_layer=2, n_head=2, n_embd=32)


def test_multi_head_joins_the_heads_back_to_full_width():
    torch.manual_seed(0)
    assert MultiHead(SMALL)(torch.randn(3, 16, 32)).shape == (3, 16, 32)


def test_block_keeps_the_shape_and_adds_to_its_input():
    torch.manual_seed(0)
    block = Block(SMALL)
    x = torch.randn(2, 16, 32)
    out = block(x)
    assert out.shape == x.shape
    for p in list(block.attn.proj.parameters()) + list(block.ff.net[2].parameters()):
        torch.nn.init.zeros_(p)  # silence both sub-layers: only the residual path is left
    assert torch.allclose(block(x), x)


def test_gpt_shapes_and_loss():
    torch.manual_seed(0)
    model = GPT(SMALL)
    idx = torch.randint(65, (4, 16))
    logits, loss = model(idx)
    assert logits.shape == (4, 16, 65) and loss is None
    _, loss = model(idx, torch.randint(65, (4, 16)))
    assert 3.5 < loss.item() < 5.5
    assert model(idx[:, :5])[0].shape == (4, 5, 65)  # shorter than the window is fine


def test_gpt_parameter_count_matches_the_lesson():
    model = GPT(SMALL)
    assert model(torch.randint(65, (1, 4)))[0].shape == (1, 4, 65)
    assert sum(p.numel() for p in model.parameters()) == 30017


def test_gpt_rejects_input_longer_than_its_window():
    with pytest.raises(ValueError, match="16"):
        GPT(SMALL)(torch.randint(65, (1, 17)))


def test_gpt_cannot_see_the_future():
    torch.manual_seed(0)
    model = GPT(SMALL).eval()
    idx = torch.randint(65, (1, 16))
    changed = idx.clone()
    changed[0, 15] = (changed[0, 15] + 1) % 65
    a, b = model(idx)[0], model(changed)[0]
    assert torch.allclose(a[0, :15], b[0, :15], atol=1e-5) and not torch.allclose(a[0, 15], b[0, 15])


def test_position_matters():
    torch.manual_seed(0)
    model = GPT(SMALL).eval()
    out = model(torch.tensor([[7, 7, 7, 7]]))[0]
    assert not torch.allclose(out[0, 0], out[0, 3], atol=1e-4)  # same token, different place, different prediction


def test_gpt_can_memorise_one_batch():
    torch.manual_seed(0)
    model = GPT(SMALL)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-2)
    x, y = torch.randint(65, (4, 16)), torch.randint(65, (4, 16))
    for _ in range(200):
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    assert loss.item() < 0.3


def test_estimate_loss_measures_without_disturbing_the_model():
    torch.manual_seed(0)
    model = GPT(SMALL)
    data = torch.randint(65, (500,))
    g = torch.Generator().manual_seed(0)
    value = estimate_loss(model, data, 16, batches=3, batch_size=4, generator=g)
    assert isinstance(value, float) and 3.5 < value < 5.5
    assert model.training is True and all(p.grad is None for p in model.parameters())
    model.eval()
    estimate_loss(model, data, 16, batches=1, batch_size=4, generator=g)
    assert model.training is False
