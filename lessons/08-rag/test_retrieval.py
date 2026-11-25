"""Tests for session 8. Run from the course app, or: pytest lessons/08-rag -q"""
import os

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.retrieval import bm25_scores, build_context, chunk, rrf
else:
    from retrieval import bm25_scores, build_context, chunk, rrf

TWELVE = " ".join(f"w{i}" for i in range(1, 13))
# The three tiny documents worked through in the lesson.
DOCS = [["payment", "failed", "card"], ["card", "declined", "card", "expired"], ["search", "slow"]]
NEIGHBOURS = [
    {"number": "INC0010011", "priority": 3, "service": "payments", "short_description": "Refunds taking more than 10 days",
     "resolution": "Root cause: the refund batch was under-provisioned. Fix: doubled the nightly batch."},
    {"number": "INC0010044", "priority": 4, "service": "payments", "short_description": "Customers chasing refunds",
     "resolution": "Root cause: schedule change by a carrier. Fix: added refund workers."},
    {"number": "INC0010301", "priority": 2, "service": "identity", "short_description": "Login loop on mobile",
     "resolution": "Root cause: expired certificate. Fix: renewed it."},
]


def test_chunk_on_the_lesson_example():
    assert chunk(TWELVE, 5, 2) == ["w1 w2 w3 w4 w5", "w4 w5 w6 w7 w8", "w7 w8 w9 w10 w11", "w10 w11 w12"]


def test_chunk_edges():
    assert chunk("only three words", 5, 2) == ["only three words"]
    assert chunk("", 5, 2) == [] and chunk("   ", 5, 2) == []
    assert chunk("a b c d e", 5, 2) == ["a b c d e"]          # exactly one full piece, no stub after it
    assert chunk("a  b\n c\td e f", 3, 0) == ["a b c", "d e f"]   # any whitespace separates words


def test_chunks_cover_every_word_and_overlap_as_asked():
    pieces = chunk(" ".join(str(i) for i in range(103)), 20, 5)
    assert pieces[0].split()[-5:] == pieces[1].split()[:5]
    assert all(len(p.split()) <= 20 for p in pieces) and pieces[-1].split()[-1] == "102"
    assert {w for p in pieces for w in p.split()} == {str(i) for i in range(103)}


def test_bm25_on_the_lesson_example():
    assert [round(s, 4) for s in bm25_scores(["card", "payment"], DOCS)] == [1.4508, 0.6065, 0.0]


def test_bm25_rewards_rare_words_and_discounts_repetition_and_length():
    rare, common = bm25_scores(["payment"], DOCS)[0], bm25_scores(["card"], DOCS)[0]
    assert rare > common                                           # "payment" is in one document, "card" in two
    once = bm25_scores(["card"], [["card", "x", "y", "z"], ["a", "b", "c", "d"]])[0]
    twice = bm25_scores(["card"], [["card", "card", "y", "z"], ["a", "b", "c", "d"]])[0]
    assert once < twice < 2 * once                                 # a second mention helps, but less than the first
    short, long = bm25_scores(["card"], [["card", "x"], ["card", "x", "y", "z", "w", "v"]])
    assert short > long


def test_rrf_on_the_lesson_example():
    assert rrf([["a", "b", "c"], ["b", "c", "d"]]) == ["b", "c", "a", "d"]


def test_rrf_with_one_list_keeps_its_order_and_agreement_beats_one_first_place():
    assert rrf([["x", "y", "z"]]) == ["x", "y", "z"]
    assert rrf([["solo", "both"], ["both", "other"]])[0] == "both"
    assert rrf([["a", "b"], ["b", "a"]], k=1) in (["a", "b"], ["b", "a"])   # a perfect tie may go either way


def test_context_lists_each_incident_with_its_outcome():
    text = build_context(NEIGHBOURS, 10_000)
    assert text.startswith("INC0010011 | P3 | payments | Refunds taking more than 10 days\nResolution: Root cause: the refund batch")
    assert text.count("\n\n") == 2 and "INC0010301 | P2 | identity | Login loop on mobile" in text
    assert text.index("INC0010011") < text.index("INC0010044") < text.index("INC0010301")


def test_context_stays_within_the_budget_without_cutting_a_block():
    two = build_context(NEIGHBOURS[:2], 10_000)
    text = build_context(NEIGHBOURS, len(two) + 20)       # room for two blocks and a little more, not for three
    assert text == two and len(text) <= len(two) + 20
    assert build_context(NEIGHBOURS, 10) == "" and build_context([], 500) == ""
