"""Experiments for session 2. Run from the project folder, for example:

    python lessons/02-next-token/train.py
    python lessons/02-next-token/train.py --lr 0.001
    python lessons/02-next-token/train.py --show-row P
    python lessons/02-next-token/train.py --gradcheck
"""
import argparse
import sys
import time
from pathlib import Path

import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bigram import BigramModel, get_batch, train_step  # noqa: E402
from labkit import CharTokenizer, load_corpus, save_run  # noqa: E402


def gradcheck() -> None:
    logits = torch.tensor([2.0, 1.0, 0.1], requires_grad=True)
    loss = F.cross_entropy(logits.unsqueeze(0), torch.tensor([0]))
    loss.backward()
    probs = F.softmax(logits.detach(), dim=0)
    print("probabilities        ", [round(p, 4) for p in probs.tolist()])
    print("gradient from PyTorch", [round(g, 4) for g in logits.grad.tolist()])
    print("Compare with your hand calculation: probability minus 1 for the target, probability for the rest.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--lr", type=float, default=0.01)
    ap.add_argument("--sample", type=int, default=300, help="characters to generate after training")
    ap.add_argument("--show-row", help="print the 8 most likely characters after this one")
    ap.add_argument("--gradcheck", action="store_true", help="show the gradient for the lesson's three-score example")
    args = ap.parse_args()
    if args.gradcheck:
        return gradcheck()

    text = load_corpus()
    tok = CharTokenizer(text)
    data = torch.tensor(tok.encode(text))
    torch.manual_seed(1337)
    g = torch.Generator().manual_seed(1337)
    model = BigramModel(tok.vocab_size)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)
    print(f"{len(data):,} characters, vocabulary of {tok.vocab_size}. A uniform guess would score {torch.tensor(float(tok.vocab_size)).log():.3f}.")

    steps, losses, started = [], [], time.time()
    for step in range(args.steps + 1):
        loss = train_step(model, opt, *get_batch(data, 8, 32, g))
        if step % (args.steps // 10 or 1) == 0:
            steps.append(step)
            losses.append(round(loss, 4))
            print(f"step {step:>5}  loss {loss:.3f}")
    save_run(f"bigram-lr{args.lr}", {"config": {"model": "bigram", "lr": args.lr}, "steps": steps,
                                      "train_loss": losses, "val_loss": [], "seconds": round(time.time() - started, 1)})

    if args.show_row:
        row = F.softmax(model.table.weight[tok.encode(args.show_row[0])[0]].detach(), dim=0)
        top = torch.topk(row, 8)
        print(f"\nAfter {args.show_row[0]!r} the model expects:")
        for p, i in zip(top.values.tolist(), top.indices.tolist()):
            print(f"  {tok.decode([i])!r:>6}  {p:.2f}")
    if args.sample:
        out = model.generate(torch.tensor([tok.encode("\n")]), args.sample, generator=g)
        print("\n--- sample ---" + tok.decode(out[0].tolist()))


if __name__ == "__main__":
    main()
