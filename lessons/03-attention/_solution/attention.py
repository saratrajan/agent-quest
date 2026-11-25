"""Reference solution for session 3. Try the gaps in ../attention.py yourself first."""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def attention_by_hand(query: list[float], keys: list[list[float]], values: list[list[float]]):
    # >>> YOUR CODE
    scale = math.sqrt(len(query))
    scores = [sum(q * k for q, k in zip(query, key)) / scale for key in keys]
    top = max(scores)
    exps = [math.exp(s - top) for s in scores]
    weights = [e / sum(exps) for e in exps]
    out = [sum(w * v[i] for w, v in zip(weights, values)) for i in range(len(values[0]))]
    return weights, out
    # <<< YOUR CODE


def causal_mask(T: int) -> torch.Tensor:
    # >>> YOUR CODE
    return torch.tril(torch.ones(T, T, dtype=torch.bool))
    # <<< YOUR CODE


def scaled_dot_product(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, mask: torch.Tensor | None = None):
    # >>> YOUR CODE
    scores = q @ k.transpose(-2, -1) / math.sqrt(k.shape[-1])
    if mask is not None:
        scores = scores.masked_fill(~mask, float("-inf"))
    weights = F.softmax(scores, dim=-1)
    return weights @ v, weights
    # <<< YOUR CODE


class Head(nn.Module):
    def __init__(self, n_embd: int, head_size: int, block_size: int):
        super().__init__()
        self.key = nn.Linear(n_embd, head_size, bias=False)
        self.query = nn.Linear(n_embd, head_size, bias=False)
        self.value = nn.Linear(n_embd, head_size, bias=False)
        self.register_buffer("mask", causal_mask(block_size))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # >>> YOUR CODE
        T = x.shape[1]
        out, _ = scaled_dot_product(self.query(x), self.key(x), self.value(x), self.mask[:T, :T])
        return out
        # <<< YOUR CODE
