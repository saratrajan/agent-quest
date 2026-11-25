"""Tests for your tokenizer. The course app runs these when you press
"Run the tests"; you can also run `pytest lessons/01-tokenization -q`."""
import os

if os.environ.get("LAB_SOLUTIONS") == "1":
    from _solution.bpe import decode, encode, get_pair_counts, merge, train
else:
    from bpe import decode, encode, get_pair_counts, merge, train


def test_pair_counts():
    assert get_pair_counts([1, 2, 3, 1, 2]) == {(1, 2): 2, (2, 3): 1, (3, 1): 1}


def test_merge_non_overlapping():
    assert merge([5, 5, 5, 5, 5], (5, 5), 9) == [9, 9, 5]


def test_train_textbook_example():
    merges = train("aaabdaaabac", 259)
    assert merges == {(97, 97): 256, (256, 97): 257, (257, 98): 258}


def test_encode_textbook_example():
    assert encode("aaabdaaabac", train("aaabdaaabac", 259)) == [258, 100, 258, 97, 99]


def test_round_trip_unicode():
    t = "Zürich → Kraków booking failed ✈ 503"
    m = train(t * 3, 300)
    assert decode(encode(t, m), m) == t


def test_train_stops_when_nothing_repeats():
    assert train("abc", 300) == {}


def test_empty_text():
    assert train("", 300) == {} and encode("", {}) == []


def test_compresses_incident_text():
    text = "payment gateway timeout " * 50
    assert len(encode(text, train(text, 300))) < len(text.encode()) / 3
