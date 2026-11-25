"""Session 8: the retrieval half of RAG, written by you.

Retrieval-augmented generation is two steps: find the passages worth
reading, then put them in the prompt. The vector database is adopted this
session (see store.py); what you write here are the four ideas around it
that decide whether retrieval is any good.

Fill the four gaps marked YOUR CODE (about 40 lines in total).
"""
import math
from collections import Counter


def chunk(text: str, size: int, overlap: int) -> list[str]:
    """Split a long text into pieces of at most `size` words, each piece
    starting `size - overlap` words after the one before, so neighbouring
    pieces share `overlap` words. The last piece ends at the end of the text.
    A text of `size` words or fewer is one piece; an empty text is no pieces.
    Split on whitespace with text.split() and join pieces back with spaces."""
    # >>> YOUR CODE (about 8 lines)
    words = text.split()
    pieces, start = [], 0
    while start < len(words):
        pieces.append(" ".join(words[start:start + size]))
        if start + size >= len(words):
            break
        start += size - overlap
    return pieces
    # <<< YOUR CODE


def bm25_scores(query: list[str], docs: list[list[str]], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Keyword relevance, the long-standing default of search engines. One
    score per document, for a query and documents already split into words.

    For each query word t that occurs f times in a document of length L:
        idf(t) = ln( (N - n + 0.5) / (n + 0.5) + 1 )      N documents, n of them contain t
        score += idf(t) * f * (k1 + 1) / ( f + k1 * (1 - b + b * L / average_length) )
    A word that is rare across the documents counts for more (idf); repeating
    a word helps less each time (the f on both sides); long documents are
    marked down (L / average_length).
    """
    # >>> YOUR CODE (about 12 lines)
    n_docs = len(docs)
    average = sum(len(d) for d in docs) / n_docs
    containing = Counter(word for d in docs for word in set(d))
    scores = []
    for d in docs:
        counts, total = Counter(d), 0.0
        for t in query:
            f = counts[t]
            if f:
                idf = math.log((n_docs - containing[t] + 0.5) / (containing[t] + 0.5) + 1)
                total += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(d) / average))
        scores.append(total)
    return scores
    # <<< YOUR CODE


def rrf(rankings: list[list[str]], k: int = 60) -> list[str]:
    """Reciprocal rank fusion: merge several ranked lists of ids into one.
    An id at position r (counting from 1) in a list earns 1 / (k + r) from
    that list; add up what each id earns across all lists and return the ids
    from highest total to lowest. It needs no scores, only orderings, which
    is why it can combine keyword and vector search."""
    # >>> YOUR CODE (about 5 lines)
    totals: dict[str, float] = {}
    for ranking in rankings:
        for position, doc_id in enumerate(ranking, 1):
            totals[doc_id] = totals.get(doc_id, 0.0) + 1 / (k + position)
    return sorted(totals, key=totals.get, reverse=True)
    # <<< YOUR CODE


def build_context(neighbours: list[dict], max_chars: int) -> str:
    """The retrieved incidents, laid out for the prompt, within a budget.

    One block per incident, best first, in this form (two lines):
        INC0010011 | P3 | payments | Refunds taking more than 10 days
        Resolution: Root cause: ... Fix: ...
    Blocks are separated by a blank line. Add blocks in order and stop before
    the one that would take the text over max_chars: never cut a block in half.
    """
    # >>> YOUR CODE (about 8 lines)
    text = ""
    for n in neighbours:
        block = (f"{n['number']} | P{n['priority']} | {n['service']} | {n['short_description']}\n"
                 f"Resolution: {n['resolution']}")
        candidate = block if not text else text + "\n\n" + block
        if len(candidate) > max_chars:
            break
        text = candidate
    return text
    # <<< YOUR CODE
