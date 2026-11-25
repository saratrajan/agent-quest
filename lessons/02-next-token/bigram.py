"""Session 2: the simplest language model, written by you.

A bigram model predicts the next token from the current token alone. It is
too simple to be useful and exactly simple enough to show every part of
training: batches, logits, loss, gradients, an optimizer step.

Fill the four gaps marked YOUR CODE (about 20 lines in total). `generate` is given.
"""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def cross_entropy_by_hand(logits: list[float], target: int) -> float:
    """The loss for one prediction, in plain Python.

    Turn the scores into probabilities with softmax, then return minus the
    log of the probability given to the correct token:
        [2.0, 1.0, 0.1] with target 0  ->  0.4170
    Subtract the largest score from every score before calling math.exp, or
    large scores will overflow.
    """
    # >>> YOUR CODE (about 3 lines)
    raise NotImplementedError("cross_entropy_by_hand is yours to write")
    # <<< YOUR CODE


def get_batch(data: torch.Tensor, block_size: int, batch_size: int, generator=None):
    """Pick `batch_size` random windows of `block_size` tokens from `data`.

    Returns (x, y), each of shape (batch_size, block_size). y is the same
    window moved one place to the right: y[b, t] is the token that follows x[b, t].
    Use torch.randint(..., generator=generator) for the start positions.
    """
    # >>> YOUR CODE (about 4 lines)
    raise NotImplementedError("get_batch is yours to write")
    # <<< YOUR CODE


class BigramModel(nn.Module):
    def __init__(self, vocab_size: int):
        super().__init__()
        # Row i holds the scores for "which token follows token i".
        self.table = nn.Embedding(vocab_size, vocab_size)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        """idx has shape (B, T). Return (logits, loss).

        logits has shape (B, T, vocab): look each token up in self.table.
        Without targets, loss is None. With targets, flatten logits to
        (B*T, vocab) and targets to (B*T,) and use F.cross_entropy.
        """
        # >>> YOUR CODE (about 6 lines)
        raise NotImplementedError("BigramModel.forward is yours to write")
        # <<< YOUR CODE

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new_tokens: int, generator=None) -> torch.Tensor:
        """Given: extend idx one sampled token at a time."""
        for _ in range(max_new_tokens):
            logits, _ = self(idx)
            probs = F.softmax(logits[:, -1, :], dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs, 1, generator=generator)], dim=1)
        return idx


def train_step(model: nn.Module, optimizer: torch.optim.Optimizer, xb: torch.Tensor, yb: torch.Tensor) -> float:
    """One step of learning. Clear old gradients, compute the loss, work out
    the gradients, let the optimizer move the weights. Return the loss as a float."""
    # >>> YOUR CODE (about 5 lines)
    raise NotImplementedError("train_step is yours to write")
    # <<< YOUR CODE
