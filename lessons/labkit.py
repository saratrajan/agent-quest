"""Shared helpers for the lessons: the corpus, a character tokenizer, device
choice, and saving training runs so the course app can chart them."""
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path


def load_corpus(path: str = "data/corpus.txt") -> str:
    p = Path(path)
    if not p.exists():
        sys.exit(f"{path} is missing. Run `make data` first, from the project folder.")
    return p.read_text()


class CharTokenizer:
    """One token per distinct character. Sessions 2 to 4 use this so the
    vocabulary is small enough to print and inspect."""

    def __init__(self, text: str):
        self.chars = sorted(set(text))
        self.vocab_size = len(self.chars)
        self._to_id = {c: i for i, c in enumerate(self.chars)}

    def encode(self, text: str) -> list[int]:
        try:
            return [self._to_id[c] for c in text]
        except KeyError as err:
            raise ValueError(f"The character {err.args[0]!r} is not in the vocabulary this tokenizer was built from.") from None

    def decode(self, ids) -> str:
        return "".join(self.chars[int(i)] for i in ids)


def pick_device() -> str:
    import torch

    if torch.backends.mps.is_available():
        return "mps"
    return "cuda" if torch.cuda.is_available() else "cpu"


def save_run(name: str, record: dict, runs_dir: str = "data/runs") -> str:
    """Save one training run as data/runs/<name>.json for the loss chart."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,60}", name):
        raise ValueError("A run name may use letters, digits, dot, dash and underscore only.")
    out = Path(runs_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.json"
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    path.write_text(json.dumps({**record, "name": name, "saved_at": stamp}, indent=1))
    return str(path)
