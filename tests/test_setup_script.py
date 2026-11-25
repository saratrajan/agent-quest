"""setup.sh must never assume a tool is installed, and --check must change nothing."""
import os
import stat
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path("setup.sh").resolve()


def stub(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


def run(args, path_dirs, cwd=None):
    env = {"PATH": os.pathsep.join([str(p) for p in path_dirs] + ["/usr/bin", "/bin"]), "HOME": os.environ.get("HOME", "/tmp"),
           "NO_COLOR": "1"}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, cwd=cwd or SCRIPT.parent, timeout=120)


def test_script_exists_and_is_executable():
    assert SCRIPT.is_file() and os.access(SCRIPT, os.X_OK)
    assert SCRIPT.read_text().startswith("#!/usr/bin/env bash")


def test_check_reports_missing_ollama_and_changes_nothing(tmp_path):
    before = sorted(p.name for p in SCRIPT.parent.iterdir())
    out = run(["--check"], [tmp_path])  # an empty folder on PATH: no ollama, no docker
    assert out.returncode == 0, out.stderr
    text = out.stdout
    assert "Ollama" in text and "not installed" in text and "ollama.com/download" in text
    assert "Buddy" in text  # says what you lose without it
    assert "Docker" in text and "optional" in text.lower()
    assert sorted(p.name for p in SCRIPT.parent.iterdir()) == before


def test_check_sees_ollama_running_with_the_model(tmp_path):
    stub(tmp_path, "ollama", 'if [ "$1" = "list" ]; then printf "NAME ID SIZE\\nqwen3:4b abc 2.5GB\\n"; fi')
    stub(tmp_path, "curl", "exit 0")
    text = run(["--check"], [tmp_path]).stdout
    assert "Ollama is installed" in text and "Ollama is running" in text and "qwen3:4b is downloaded" in text


def test_check_sees_ollama_installed_but_not_running_and_model_missing(tmp_path):
    stub(tmp_path, "ollama", 'if [ "$1" = "list" ]; then printf "NAME ID SIZE\\n"; fi')
    stub(tmp_path, "curl", "exit 7")
    text = run(["--check"], [tmp_path]).stdout
    assert "Ollama is installed" in text and "not running" in text and "ollama serve" in text
    assert "qwen3:4b" in text and "not downloaded" in text and "2.5 GB" in text


def test_check_in_a_fresh_copy_says_what_setup_would_do(tmp_path):
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "pyproject.toml").write_text("[project]\nname='x'\n")
    out = run(["--check"], [tmp_path], cwd=fresh)
    assert out.returncode == 0
    assert "environment" in out.stdout.lower() and "not set up" in out.stdout
    assert "incident data" in out.stdout.lower() and not (fresh / ".venv").exists() and not (fresh / "data").exists()


def test_unknown_option_is_rejected_with_usage(tmp_path):
    out = run(["--frobnicate"], [tmp_path])
    assert out.returncode == 2 and "Usage" in out.stdout + out.stderr


def test_help_lists_the_three_ways_to_run(tmp_path):
    text = run(["--help"], [tmp_path]).stdout
    assert "--check" in text and "--yes" in text and "asks before" in text
