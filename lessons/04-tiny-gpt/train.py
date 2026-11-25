"""Train your GPT on the incident threads. Run from the project folder:

    python lessons/04-tiny-gpt/train.py                       # the base run
    python lessons/04-tiny-gpt/train.py --layers 1 --name one-layer
    python lessons/04-tiny-gpt/train.py --block 32 --name short-context
    python lessons/04-tiny-gpt/train.py --tokens bpe --name bpe-512

Each run is saved to data/runs/ and appears on the loss chart in the lesson.
"""
import argparse
import json
import sys
import time
from pathlib import Path

import torch

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
from gpt import GPT, estimate_loss  # noqa: E402
from labkit import CharTokenizer, load_corpus, pick_device, save_run  # noqa: E402
from parts import Config, get_batch  # noqa: E402


def bpe_tokens(text: str, vocab: int = 512):
    """Encode the corpus with the byte-pair tokenizer you wrote in session 1. Cached, because it is slow."""
    sys.path.insert(0, str(HERE.parent / "01-tokenization"))
    from bpe import decode, encode, train

    cache = Path(f"data/bpe-{vocab}.json")
    if cache.exists():
        saved = json.loads(cache.read_text())
        merges = {tuple(pair): new_id for pair, new_id in saved["merges"]}
        ids = saved["ids"]
    else:
        print(f"Training your session 1 tokenizer to a vocabulary of {vocab} and encoding the corpus. About two minutes, once.")
        merges = train(text[:150_000], vocab)
        ids = encode(text, merges)
        cache.write_text(json.dumps({"merges": [[list(p), i] for p, i in merges.items()], "ids": ids}))
    return ids, vocab, (lambda t: encode(t, merges)), (lambda i: decode(list(i), merges))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="base")
    ap.add_argument("--layers", type=int, default=4)
    ap.add_argument("--heads", type=int, default=4)
    ap.add_argument("--embd", type=int, default=128)
    ap.add_argument("--block", type=int, default=128)
    ap.add_argument("--steps", type=int, default=2000)
    ap.add_argument("--batch", type=int, default=64)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--tokens", choices=["char", "bpe"], default="char")
    ap.add_argument("--sample", type=int, default=400)
    args = ap.parse_args()

    text = load_corpus()
    if args.tokens == "bpe":
        ids, vocab, enc, dec = bpe_tokens(text)
    else:
        tok = CharTokenizer(text)
        ids, vocab, enc, dec = tok.encode(text), tok.vocab_size, tok.encode, tok.decode
    data = torch.tensor(ids)
    split = int(0.9 * len(data))
    train_data, val_data = data[:split], data[split:]

    device = pick_device()
    torch.manual_seed(1337)
    g = torch.Generator().manual_seed(1337)
    cfg = Config(vocab_size=vocab, block_size=args.block, n_layer=args.layers, n_head=args.heads, n_embd=args.embd)
    model = GPT(cfg).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"Run '{args.name}' on {device}: {n_params:,} parameters, {len(train_data):,} training tokens, vocabulary {vocab}.")
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    steps, train_loss, val_loss, started = [], [], [], time.time()
    every = max(1, args.steps // 10)
    for step in range(args.steps + 1):
        if step % every == 0:
            tl = estimate_loss(model, train_data, args.block, 10, args.batch, g, device)
            vl = estimate_loss(model, val_data, args.block, 10, args.batch, g, device)
            steps.append(step); train_loss.append(round(tl, 4)); val_loss.append(round(vl, 4))
            print(f"step {step:>5}  train {tl:.3f}  validation {vl:.3f}  ({time.time() - started:.0f}s)")
        _, loss = model(*get_batch(train_data, args.block, args.batch, g, device))
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
    seconds = round(time.time() - started, 1)
    save_run(args.name, {"config": {**vars(cfg), "tokens": args.tokens, "lr": args.lr, "parameters": n_params},
                         "steps": steps, "train_loss": train_loss, "val_loss": val_loss, "seconds": seconds})
    print(f"Finished in {seconds:.0f}s. Saved as data/runs/{args.name}.json")
    if args.tokens == "char":  # session 5 loads this to compare your model with a real one
        Path("data/checkpoints").mkdir(parents=True, exist_ok=True)
        torch.save({"state": model.state_dict(), "config": vars(cfg), "chars": tok.chars}, f"data/checkpoints/{args.name}.pt")
    if args.sample:
        start = torch.tensor([enc("\n")], device=device)
        out = model.generate(start, args.sample, generator=g)
        print("\n--- sample ---" + dec(out[0].tolist()))


if __name__ == "__main__":
    main()
