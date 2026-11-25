"""Session 4: a GPT, assembled by you.

parts.py holds what you built before: an attention head, a feed-forward
layer and get_batch. Here you put them together: several heads side by
side, a block with residual connections, the whole model, and an honest
way to measure its loss.

Fill the four gaps marked YOUR CODE (about 20 lines in total).
"""
import torch
import torch.nn as nn
import torch.nn.functional as F
from parts import Config, FeedForward, Head, get_batch


class MultiHead(nn.Module):
    """Several heads run side by side. Each sees the same input and produces
    n_embd / n_head numbers per position."""

    def __init__(self, cfg: Config):
        super().__init__()
        size = cfg.n_embd // cfg.n_head
        self.heads = nn.ModuleList([Head(cfg.n_embd, size, cfg.block_size) for _ in range(cfg.n_head)])
        self.proj = nn.Linear(cfg.n_embd, cfg.n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Run every head on x, join their outputs along the last dimension
        with torch.cat (giving n_embd numbers again), then apply self.proj."""
        # >>> YOUR CODE (about 2 lines)
        raise NotImplementedError("MultiHead.forward is yours to write")
        # <<< YOUR CODE


class Block(nn.Module):
    """One transformer block: attention to gather, feed-forward to think."""

    def __init__(self, cfg: Config):
        super().__init__()
        self.ln1, self.attn = nn.LayerNorm(cfg.n_embd), MultiHead(cfg)
        self.ln2, self.ff = nn.LayerNorm(cfg.n_embd), FeedForward(cfg.n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Two residual steps. Each normalises x, runs a sub-layer on the
        result, and ADDS that to x:
            x = x + attention(norm1(x))
            x = x + feed_forward(norm2(x))
        """
        # >>> YOUR CODE (about 3 lines)
        raise NotImplementedError("Block.forward is yours to write")
        # <<< YOUR CODE


class GPT(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.n_embd)   # what each token is
        self.pos_emb = nn.Embedding(cfg.block_size, cfg.n_embd)   # where each position is
        self.blocks = nn.Sequential(*[Block(cfg) for _ in range(cfg.n_layer)])
        self.ln_f = nn.LayerNorm(cfg.n_embd)
        self.head = nn.Linear(cfg.n_embd, cfg.vocab_size)         # back to a score per token

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        """idx has shape (B, T). Return (logits, loss) as in session 2.

        1. If T is larger than cfg.block_size, raise a ValueError that says so.
        2. x = token embeddings + position embeddings. Positions are
           torch.arange(T, device=idx.device).
        3. Run x through self.blocks, then self.ln_f, then self.head.
        4. Without targets the loss is None; with them, flatten and use F.cross_entropy.
        """
        # >>> YOUR CODE (about 9 lines)
        raise NotImplementedError("GPT.forward is yours to write")
        # <<< YOUR CODE

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new_tokens: int, generator=None) -> torch.Tensor:
        """Given: extend idx one sampled token at a time, keeping only the last block_size tokens as context."""
        for _ in range(max_new_tokens):
            logits, _ = self(idx[:, -self.cfg.block_size:])
            probs = F.softmax(logits[:, -1, :], dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs.cpu(), 1, generator=generator).to(idx.device)], dim=1)
        return idx


@torch.no_grad()
def estimate_loss(model: nn.Module, data: torch.Tensor, block_size: int, batches: int = 20,
                  batch_size: int = 32, generator=None, device: str = "cpu") -> float:
    """The average loss over several batches of `data`, as a float.

    Remember whether the model was in training mode, switch it to evaluation
    mode with model.eval(), measure, then put it back the way you found it.
    Use get_batch(data, block_size, batch_size, generator, device).
    """
    # >>> YOUR CODE (about 7 lines)
    raise NotImplementedError("estimate_loss is yours to write")
    # <<< YOUR CODE
