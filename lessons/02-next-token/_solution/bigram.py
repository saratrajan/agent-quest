"""Reference solution for session 2. Try the gaps in ../bigram.py yourself first."""
import math

import torch
import torch.nn as nn
import torch.nn.functional as F


def cross_entropy_by_hand(logits: list[float], target: int) -> float:
    # >>> YOUR CODE
    top = max(logits)  # subtracting the largest score keeps exp() from overflowing
    exps = [math.exp(x - top) for x in logits]
    return -math.log(exps[target] / sum(exps))
    # <<< YOUR CODE


def get_batch(data: torch.Tensor, block_size: int, batch_size: int, generator=None):
    # >>> YOUR CODE
    starts = torch.randint(len(data) - block_size, (batch_size,), generator=generator)
    x = torch.stack([data[i:i + block_size] for i in starts])
    y = torch.stack([data[i + 1:i + block_size + 1] for i in starts])
    return x, y
    # <<< YOUR CODE


class BigramModel(nn.Module):
    def __init__(self, vocab_size: int):
        super().__init__()
        self.table = nn.Embedding(vocab_size, vocab_size)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        # >>> YOUR CODE
        logits = self.table(idx)  # (B, T, vocab)
        if targets is None:
            return logits, None
        B, T, C = logits.shape
        loss = F.cross_entropy(logits.view(B * T, C), targets.view(B * T))
        return logits, loss
        # <<< YOUR CODE

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new_tokens: int, generator=None) -> torch.Tensor:
        for _ in range(max_new_tokens):
            logits, _ = self(idx)
            probs = F.softmax(logits[:, -1, :], dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs, 1, generator=generator)], dim=1)
        return idx


def train_step(model: nn.Module, optimizer: torch.optim.Optimizer, xb: torch.Tensor, yb: torch.Tensor) -> float:
    # >>> YOUR CODE
    optimizer.zero_grad(set_to_none=True)
    _, loss = model(xb, yb)
    loss.backward()
    optimizer.step()
    return loss.item()
    # <<< YOUR CODE
