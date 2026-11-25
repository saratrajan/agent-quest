"""Experiments for session 3. Run from the project folder:

    python lessons/03-attention/explore.py --scaling
    python lessons/03-attention/explore.py --pattern "Card payments failing"
    python lessons/03-attention/explore.py --no-mask
"""
import argparse
import sys
import time
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attention import Head, causal_mask, scaled_dot_product  # noqa: E402
from labkit import CharTokenizer, load_corpus  # noqa: E402

BLOCK, EMBD = 32, 32


class OneHeadModel(nn.Module):
    """Given: the smallest model that uses your Head. Session 4 grows this into a GPT."""

    def __init__(self, vocab: int, masked: bool = True):
        super().__init__()
        self.tok, self.pos = nn.Embedding(vocab, EMBD), nn.Embedding(BLOCK, EMBD)
        self.head = Head(EMBD, EMBD, BLOCK)
        if not masked:
            self.head.mask.fill_(True)  # every position may look anywhere, including ahead
        self.out = nn.Linear(EMBD, vocab)

    def embed(self, idx):
        return self.tok(idx) + self.pos(torch.arange(idx.shape[1]))

    def forward(self, idx, targets=None):
        logits = self.out(self.head(self.embed(idx)))
        loss = None if targets is None else F.cross_entropy(logits.view(-1, logits.shape[-1]), targets.view(-1))
        return logits, loss


def train(model, data, steps, g):
    opt = torch.optim.AdamW(model.parameters(), lr=3e-3)
    for step in range(steps + 1):
        ix = torch.randint(len(data) - BLOCK, (32,), generator=g)
        x = torch.stack([data[i:i + BLOCK] for i in ix])
        y = torch.stack([data[i + 1:i + BLOCK + 1] for i in ix])
        _, loss = model(x, y)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if step % (steps // 5) == 0:
            print(f"  step {step:>5}  loss {loss.item():.3f}")
    return loss.item()


def scaling() -> None:
    torch.manual_seed(0)
    print("Largest attention weight in a row of 16 tokens, averaged over 200 random rows:")
    for d in (4, 64, 512):
        q, k = torch.randn(200, 1, d), torch.randn(200, 16, d)
        raw = F.softmax(q @ k.transpose(-2, -1), dim=-1).max(-1).values.mean().item()
        _, w = scaled_dot_product(q, k, k)
        print(f"  d = {d:>3}   without scaling {raw:.2f}   with scaling {w.max(-1).values.mean().item():.2f}")
    print("A value near 1.00 means one token takes everything and the rest are ignored.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scaling", action="store_true")
    ap.add_argument("--pattern", help="train one head, then show where the last character of this text looks")
    ap.add_argument("--no-mask", action="store_true", help="train with and without the causal mask and compare")
    ap.add_argument("--steps", type=int, default=1500)
    args = ap.parse_args()
    if args.scaling:
        return scaling()

    text = load_corpus()
    tok = CharTokenizer(text)
    data = torch.tensor(tok.encode(text))
    started = time.time()
    if args.pattern:
        torch.manual_seed(1337)
        model = OneHeadModel(tok.vocab_size)
        print("Training one attention head on the incident threads:")
        train(model, data, args.steps, torch.Generator().manual_seed(1337))
        ids = torch.tensor([tok.encode(args.pattern[-BLOCK:])])
        x = model.embed(ids)
        T = ids.shape[1]
        _, w = scaled_dot_product(model.head.query(x), model.head.key(x), model.head.value(x), causal_mask(T))
        row = w[0, -1].tolist()
        print(f"\nWhere the last character {args.pattern[-1]!r} looks:")
        for ch, weight in zip(args.pattern[-BLOCK:], row):
            print(f"  {ch!r:>5} {weight:.2f} {'#' * round(weight * 40)}")
    elif args.no_mask:
        for masked in (True, False):
            torch.manual_seed(1337)
            print(f"\n{'With' if masked else 'Without'} the causal mask:")
            model = OneHeadModel(tok.vocab_size, masked=masked)
            train(model, data, args.steps, torch.Generator().manual_seed(1337))
            idx = torch.tensor([tok.encode("\n")])
            for _ in range(80):
                logits, _ = model(idx[:, -BLOCK:])
                nxt = torch.multinomial(F.softmax(logits[:, -1], dim=-1), 1)
                idx = torch.cat([idx, nxt], dim=1)
            print("  writes:", repr(tok.decode(idx[0].tolist())[1:]))
    else:
        ap.print_help()
    print(f"\n({time.time() - started:.0f}s)")


if __name__ == "__main__":
    main()
