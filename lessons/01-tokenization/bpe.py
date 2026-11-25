"""Session 1: a byte-pair encoding tokenizer, written by you.

Fill the four gaps marked YOUR CODE. Each is short; the whole file needs
under 40 lines from you. `decode` is given so you can check your work.

Run the tests from the course app, or with:
    pytest lessons/01-tokenization -q
"""


def get_pair_counts(ids: list[int]) -> dict[tuple[int, int], int]:
    """Count how often each adjacent pair occurs.

    [1, 2, 3, 1, 2] -> {(1, 2): 2, (2, 3): 1, (3, 1): 1}
    Keep pairs in the order you first meet them; `train` relies on that order.
    """
    # >>> YOUR CODE (about 5 lines)
    raise NotImplementedError("get_pair_counts is yours to write")
    # <<< YOUR CODE


def merge(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    """Replace every occurrence of `pair` with `new_id`, scanning left to right.

    Occurrences must not overlap: merging (5, 5) in [5, 5, 5, 5, 5] gives [9, 9, 5].
    """
    # >>> YOUR CODE (about 10 lines)
    raise NotImplementedError("merge is yours to write")
    # <<< YOUR CODE


def train(text: str, vocab_size: int) -> dict[tuple[int, int], int]:
    """Learn merges from `text` until the vocabulary reaches `vocab_size`.

    Start from the UTF-8 bytes of the text (ids 0 to 255). New tokens get ids
    256, 257, ... Each round: count the pairs, take the most frequent, merge it.
    When two pairs tie, take the one seen first: `max(counts, key=counts.get)`
    does exactly that. Stop early if no pair occurs at least twice.
    Returns {pair: new_id} in the order learned.
    """
    # >>> YOUR CODE (about 12 lines)
    raise NotImplementedError("train is yours to write")
    # <<< YOUR CODE


def encode(text: str, merges: dict[tuple[int, int], int]) -> list[int]:
    """Turn text into token ids by replaying the merges in the order learned."""
    # >>> YOUR CODE (about 5 lines)
    raise NotImplementedError("encode is yours to write")
    # <<< YOUR CODE


def decode(ids: list[int], merges: dict[tuple[int, int], int]) -> str:
    """Given: turn token ids back into text."""
    vocab = {i: bytes([i]) for i in range(256)}
    for (a, b), new_id in merges.items():
        vocab[new_id] = vocab[a] + vocab[b]
    return b"".join(vocab[i] for i in ids).decode("utf-8", errors="replace")
