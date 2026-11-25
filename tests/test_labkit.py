import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("lessons").resolve()))
import labkit  # noqa: E402


def test_char_tokenizer_round_trips_any_text():
    text = "Zürich → Kraków ✈ 503\nP1 payments"
    tok = labkit.CharTokenizer(text)
    assert tok.vocab_size == len(set(text)) and tok.decode(tok.encode(text)) == text
    assert tok.encode("P1") == [tok.encode("P")[0], tok.encode("1")[0]]


def test_char_tokenizer_rejects_unseen_characters_clearly():
    with pytest.raises(ValueError, match="not in the vocabulary"):
        labkit.CharTokenizer("abc").encode("abz")


def test_load_corpus_says_how_to_create_it(tmp_path):
    with pytest.raises(SystemExit, match="make data"):
        labkit.load_corpus(str(tmp_path / "missing.txt"))


def test_pick_device_is_one_of_the_known_three():
    pytest.importorskip("torch")
    assert labkit.pick_device() in {"mps", "cuda", "cpu"}


def test_save_run_writes_a_readable_record(tmp_path):
    path = labkit.save_run("tiny", {"config": {"n_layer": 2}, "steps": [0, 100], "train_loss": [4.2, 2.0],
                                    "val_loss": [4.2, 2.1], "seconds": 3.5}, runs_dir=str(tmp_path))
    rec = json.loads(Path(path).read_text())
    assert rec["name"] == "tiny" and rec["train_loss"] == [4.2, 2.0] and rec["saved_at"]


def test_save_run_rejects_names_that_could_escape_the_folder(tmp_path):
    with pytest.raises(ValueError):
        labkit.save_run("../evil", {}, runs_dir=str(tmp_path))
