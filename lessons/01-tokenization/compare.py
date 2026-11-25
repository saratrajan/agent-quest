"""Experiments for session 1. Run from the project folder, for example:

    python lessons/01-tokenization/compare.py --vocab 300
    python lessons/01-tokenization/compare.py --vocab 1000
    python lessons/01-tokenization/compare.py --show-merges 10
    python lessons/01-tokenization/compare.py --text "INC0010450"
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from bpe import decode, encode, train  # noqa: E402

SAMPLES = [
    "Card payments failing at 3-D Secure step",
    "Customers in EU-West report that the fare shown in search is lower than the fare at checkout.",
    "INC0010450 error code HTTP 503 from the supplier adapter",
]


def production_counts(texts):
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return [len(enc.encode(t)) for t in texts]
    except Exception as exc:  # first use downloads the vocabulary, which needs a connection
        print(f"(production tokenizer unavailable: {exc})")
        return [None] * len(texts)


def show(piece: bytes) -> str:
    return piece.decode("utf-8", errors="replace").replace(" ", "␣").replace("\n", "⏎")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vocab", type=int, default=512, help="vocabulary size to train to")
    ap.add_argument("--chars", type=int, default=60000, help="how much of the incident corpus to train on")
    ap.add_argument("--show-merges", type=int, default=0, help="print the first N merges learned")
    ap.add_argument("--text", action="append", help="text to tokenize (repeatable); defaults to three samples")
    args = ap.parse_args()

    corpus_path = Path("data/corpus.txt")
    if not corpus_path.exists():
        sys.exit("data/corpus.txt is missing. Run `make data` first.")
    corpus = corpus_path.read_text()[: args.chars]

    started = time.time()
    merges = train(corpus, args.vocab)
    ids = encode(corpus, merges)
    n_bytes = len(corpus.encode("utf-8"))
    print(f"Trained to a vocabulary of {256 + len(merges)} on {n_bytes:,} bytes in {time.time() - started:.1f}s")
    print(f"Corpus: {n_bytes:,} bytes -> {len(ids):,} tokens, compression ratio {n_bytes / len(ids):.2f}x")

    if args.show_merges:
        vocab = {i: bytes([i]) for i in range(256)}
        print(f"\nFirst {args.show_merges} merges:")
        for k, ((a, b), new_id) in enumerate(merges.items()):
            vocab[new_id] = vocab[a] + vocab[b]
            if k < args.show_merges:
                print(f"  {new_id}: '{show(vocab[a])}' + '{show(vocab[b])}' -> '{show(vocab[new_id])}'")

    texts = args.text or SAMPLES
    print(f"\n{'bytes':>6} {'yours':>6} {'cl100k':>7}  text")
    for text, prod in zip(texts, production_counts(texts)):
        mine = encode(text, merges)
        assert decode(mine, merges) == text, "round trip failed"
        print(f"{len(text.encode()):>6} {len(mine):>6} {prod if prod is not None else '-':>7}  {text}")


if __name__ == "__main__":
    main()
