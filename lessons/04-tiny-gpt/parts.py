"""Given parts for session 4: the pieces you already built in sessions 2 and 3,
so this session can concentrate on assembling them into a GPT."""
import math
from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F


@dataclass
class Config:
    vocab_size: int
    block_size: int = 128   # how many tokens of context
    n_layer: int = 4        # how many blocks are stacked
    n_head: int = 4         # attention heads per block
    n_embd: int = 128       # size of each token's vector


class Head(nn.Module):
    """One causal attention head, as you wrote it in session 3."""

    def __init__(self, n_embd: int, head_size: int, block_size: int):
        super().__init__()
        self.key = nn.Linear(n_embd, head_size, bias=False)
        self.query = nn.Linear(n_embd, head_size, bias=False)
        self.value = nn.Linear(n_embd, head_size, bias=False)
        self.register_buffer("mask", torch.tril(torch.ones(block_size, block_size, dtype=torch.bool)))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        T = x.shape[1]
        q, k, v = self.query(x), self.key(x), self.value(x)
        scores = q @ k.transpose(-2, -1) / math.sqrt(k.shape[-1])
        scores = scores.masked_fill(~self.mask[:T, :T], float("-inf"))
        return F.softmax(scores, dim=-1) @ v


class FeedForward(nn.Module):
    """A small two-layer network applied to each position on its own."""

    def __init__(self, n_embd: int):
        super().__init__()
        self.net = nn.Sequential(nn.Linear(n_embd, 4 * n_embd), nn.ReLU(), nn.Linear(4 * n_embd, n_embd))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


def get_batch(data: torch.Tensor, block_size: int, batch_size: int, generator=None, device: str = "cpu"):
    """As in session 2, moved to the chosen device."""
    starts = torch.randint(len(data) - block_size, (batch_size,), generator=generator)
    x = torch.stack([data[i:i + block_size] for i in starts])
    y = torch.stack([data[i + 1:i + block_size + 1] for i in starts])
    return x.to(device), y.to(device)
