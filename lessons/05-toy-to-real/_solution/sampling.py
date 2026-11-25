"""Reference solution for session 5. Try the gaps in ../sampling.py yourself first."""
import torch
import torch.nn.functional as F


def apply_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
    # >>> YOUR CODE
    return logits / temperature
    # <<< YOUR CODE


def top_k_filter(logits: torch.Tensor, k: int) -> torch.Tensor:
    # >>> YOUR CODE
    if k >= logits.shape[-1]:
        return logits
    kth_largest = torch.topk(logits, k).values[-1]
    return logits.masked_fill(logits < kth_largest, float("-inf"))
    # <<< YOUR CODE


def top_p_filter(logits: torch.Tensor, p: float) -> torch.Tensor:
    # >>> YOUR CODE
    probs, order = torch.sort(F.softmax(logits, dim=-1), descending=True)
    before = torch.cumsum(probs, dim=-1) - probs      # probability already covered before each token
    drop = order[before >= p]                         # everything after the set that reached p
    out = logits.clone()
    out[drop] = float("-inf")
    return out
    # <<< YOUR CODE


def sample_next(logits: torch.Tensor, temperature: float = 1.0, top_k: int | None = None,
                top_p: float | None = None, generator=None) -> int:
    # >>> YOUR CODE
    if temperature == 0:
        return int(torch.argmax(logits))
    logits = apply_temperature(logits, temperature)
    if top_k is not None:
        logits = top_k_filter(logits, top_k)
    if top_p is not None:
        logits = top_p_filter(logits, top_p)
    return int(torch.multinomial(F.softmax(logits, dim=-1), 1, generator=generator))
    # <<< YOUR CODE
