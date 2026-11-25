"""Reference solution for session 1. Try the gaps in ../bpe.py yourself first."""


def get_pair_counts(ids: list[int]) -> dict[tuple[int, int], int]:
    # >>> YOUR CODE
    counts: dict[tuple[int, int], int] = {}
    for pair in zip(ids, ids[1:]):
        counts[pair] = counts.get(pair, 0) + 1
    return counts
    # <<< YOUR CODE


def merge(ids: list[int], pair: tuple[int, int], new_id: int) -> list[int]:
    # >>> YOUR CODE
    out, i = [], 0
    while i < len(ids):
        if i + 1 < len(ids) and (ids[i], ids[i + 1]) == pair:
            out.append(new_id)
            i += 2
        else:
            out.append(ids[i])
            i += 1
    return out
    # <<< YOUR CODE


def train(text: str, vocab_size: int) -> dict[tuple[int, int], int]:
    # >>> YOUR CODE
    ids = list(text.encode("utf-8"))
    merges: dict[tuple[int, int], int] = {}
    for new_id in range(256, vocab_size):
        counts = get_pair_counts(ids)
        if not counts:
            break
        pair = max(counts, key=counts.get)  # ties go to the pair seen first
        if counts[pair] < 2:
            break
        ids = merge(ids, pair, new_id)
        merges[pair] = new_id
    return merges
    # <<< YOUR CODE


def encode(text: str, merges: dict[tuple[int, int], int]) -> list[int]:
    # >>> YOUR CODE
    ids = list(text.encode("utf-8"))
    for pair, new_id in merges.items():  # in the order they were learned
        ids = merge(ids, pair, new_id)
    return ids
    # <<< YOUR CODE


def decode(ids: list[int], merges: dict[tuple[int, int], int]) -> str:
    vocab = {i: bytes([i]) for i in range(256)}
    for (a, b), new_id in merges.items():
        vocab[new_id] = vocab[a] + vocab[b]
    return b"".join(vocab[i] for i in ids).decode("utf-8", errors="replace")
