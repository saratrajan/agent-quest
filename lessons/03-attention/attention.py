"""Session 3: attention, written by you.

Attention lets each position look back at earlier positions and take from
them what it needs. You write it three times: once in plain Python on a
3-token example, once as a tensor function, once as a layer.

Fill the four gaps marked YOUR CODE (about 15 lines in total).
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def attention_by_hand(query: list[float], keys: list[list[float]], values: list[list[float]]):
    """Attention for ONE query over a few tokens, in plain Python.

    1. score_j = (query . key_j) / sqrt(d), where d is the length of the query
    2. weights = softmax(scores)
    3. out = sum over j of weights_j * value_j
    Returns (weights, out) as two lists.

    query [1, 1] with keys [[1,0],[0,1],[1,1]] gives weights [0.2483, 0.2483, 0.5035].
    """
    # >>> YOUR CODE (about 6 lines)
    raise NotImplementedError("attention_by_hand is yours to write")
    # <<< YOUR CODE


def causal_mask(T: int) -> torch.Tensor:
    """A T by T boolean matrix: True where row i may look at column j, that is
    where j <= i. torch.tril does the shape for you."""
    # >>> YOUR CODE (1 line)
    raise NotImplementedError("causal_mask is yours to write")
    # <<< YOUR CODE


def scaled_dot_product(q: torch.Tensor, k: torch.Tensor, v: torch.Tensor, mask: torch.Tensor | None = None):
    """The same three steps for every position at once.

    q, k, v have shape (..., T, d). Returns (out, weights) with weights of
    shape (..., T, T). Where mask is False, set the score to -inf BEFORE the
    softmax, so those positions get a weight of exactly zero.
    """
    # >>> YOUR CODE (about 5 lines)
    raise NotImplementedError("scaled_dot_product is yours to write")
    # <<< YOUR CODE


class Head(nn.Module):
    """One attention head: three learned projections and a causal mask."""

    def __init__(self, n_embd: int, head_size: int, block_size: int):
        super().__init__()
        self.key = nn.Linear(n_embd, head_size, bias=False)
        self.query = nn.Linear(n_embd, head_size, bias=False)
        self.value = nn.Linear(n_embd, head_size, bias=False)
        self.register_buffer("mask", causal_mask(block_size))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """x has shape (B, T, n_embd). Project it to queries, keys and values,
        then call scaled_dot_product with the top-left T by T corner of
        self.mask. Return only the output, shape (B, T, head_size)."""
        # >>> YOUR CODE (about 3 lines)
        raise NotImplementedError("Head.forward is yours to write")
        # <<< YOUR CODE
