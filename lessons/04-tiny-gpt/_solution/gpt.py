"""Reference solution for session 4. Try the gaps in ../gpt.py yourself first."""
import torch
import torch.nn as nn
import torch.nn.functional as F

from parts import Config, FeedForward, Head, get_batch


class MultiHead(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        size = cfg.n_embd // cfg.n_head
        self.heads = nn.ModuleList([Head(cfg.n_embd, size, cfg.block_size) for _ in range(cfg.n_head)])
        self.proj = nn.Linear(cfg.n_embd, cfg.n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # >>> YOUR CODE
        together = torch.cat([head(x) for head in self.heads], dim=-1)
        return self.proj(together)
        # <<< YOUR CODE


class Block(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.ln1, self.attn = nn.LayerNorm(cfg.n_embd), MultiHead(cfg)
        self.ln2, self.ff = nn.LayerNorm(cfg.n_embd), FeedForward(cfg.n_embd)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # >>> YOUR CODE
        x = x + self.attn(self.ln1(x))
        x = x + self.ff(self.ln2(x))
        return x
        # <<< YOUR CODE


class GPT(nn.Module):
    def __init__(self, cfg: Config):
        super().__init__()
        self.cfg = cfg
        self.tok_emb = nn.Embedding(cfg.vocab_size, cfg.n_embd)
        self.pos_emb = nn.Embedding(cfg.block_size, cfg.n_embd)
        self.blocks = nn.Sequential(*[Block(cfg) for _ in range(cfg.n_layer)])
        self.ln_f = nn.LayerNorm(cfg.n_embd)
        self.head = nn.Linear(cfg.n_embd, cfg.vocab_size)

    def forward(self, idx: torch.Tensor, targets: torch.Tensor | None = None):
        # >>> YOUR CODE
        B, T = idx.shape
        if T > self.cfg.block_size:
            raise ValueError(f"Got {T} tokens but the context window is {self.cfg.block_size}.")
        x = self.tok_emb(idx) + self.pos_emb(torch.arange(T, device=idx.device))
        logits = self.head(self.ln_f(self.blocks(x)))
        if targets is None:
            return logits, None
        loss = F.cross_entropy(logits.view(B * T, -1), targets.view(B * T))
        return logits, loss
        # <<< YOUR CODE

    @torch.no_grad()
    def generate(self, idx: torch.Tensor, max_new_tokens: int, generator=None) -> torch.Tensor:
        for _ in range(max_new_tokens):
            logits, _ = self(idx[:, -self.cfg.block_size:])
            probs = F.softmax(logits[:, -1, :], dim=-1)
            idx = torch.cat([idx, torch.multinomial(probs.cpu(), 1, generator=generator).to(idx.device)], dim=1)
        return idx


@torch.no_grad()
def estimate_loss(model: nn.Module, data: torch.Tensor, block_size: int, batches: int = 20,
                  batch_size: int = 32, generator=None, device: str = "cpu") -> float:
    # >>> YOUR CODE
    was_training = model.training
    model.eval()
    losses = []
    for _ in range(batches):
        _, loss = model(*get_batch(data, block_size, batch_size, generator, device))
        losses.append(loss.item())
    model.train(was_training)
    return sum(losses) / len(losses)
    # <<< YOUR CODE
