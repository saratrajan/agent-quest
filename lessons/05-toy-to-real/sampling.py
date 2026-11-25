"""Session 5: choosing the next token, written by you.

A model outputs a score for every token. How one token gets picked from
those scores is a separate step with three controls: temperature, top-k and
top-p. Every model you will use exposes them; here you implement them.

Each function takes the logits for ONE position: a 1-D tensor with one score
per token. Fill the four gaps marked YOUR CODE (about 20 lines in total).
"""
import torch
import torch.nn.functional as F


def apply_temperature(logits: torch.Tensor, temperature: float) -> torch.Tensor:
    """Divide the scores by the temperature. Below 1 sharpens the
    distribution, above 1 flattens it."""
    # >>> YOUR CODE (1 line)
    raise NotImplementedError("apply_temperature is yours to write")
    # <<< YOUR CODE


def top_k_filter(logits: torch.Tensor, k: int) -> torch.Tensor:
    """Keep the k highest scores; set every other score to -inf.
    If k is at least the vocabulary size, return the logits unchanged.
    torch.topk(logits, k).values gives the k highest, largest first."""
    # >>> YOUR CODE (about 4 lines)
    raise NotImplementedError("top_k_filter is yours to write")
    # <<< YOUR CODE


def top_p_filter(logits: torch.Tensor, p: float) -> torch.Tensor:
    """Nucleus sampling. Keep the smallest set of most-likely tokens whose
    probabilities add up to at least p; set the rest to -inf.

    Sort the probabilities from high to low. A token is kept if the total
    probability of the tokens BEFORE it is still below p.
    With probabilities [0.5, 0.3, 0.15, 0.05]: p = 0.75 keeps two, p = 0.85 keeps three.
    """
    # >>> YOUR CODE (about 6 lines)
    raise NotImplementedError("top_p_filter is yours to write")
    # <<< YOUR CODE


def sample_next(logits: torch.Tensor, temperature: float = 1.0, top_k: int | None = None,
                top_p: float | None = None, generator=None) -> int:
    """Pick one token id.

    A temperature of 0 means "always the most likely token": return the
    argmax and skip everything else (dividing by zero is not an option).
    Otherwise: temperature, then top-k if given, then top-p if given, then
    softmax and one draw with torch.multinomial(..., generator=generator).
    Return a plain int.
    """
    # >>> YOUR CODE (about 8 lines)
    raise NotImplementedError("sample_next is yours to write")
    # <<< YOUR CODE
