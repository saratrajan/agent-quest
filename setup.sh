#!/usr/bin/env bash
# Agent Quest setup. Assumes nothing is installed: it checks each thing the
# project needs, sets up what it can, and asks before any sizeable download.
#
#   ./setup.sh           set everything up; asks before each download
#   ./setup.sh --check   only report what is present and what is missing
#   ./setup.sh --yes     answer yes to every question (for unattended use)

set -u

MODEL="qwen3:4b"
MODE="setup"
ASSUME_YES=0

usage() {
  cat <<'EOF'
Usage: ./setup.sh [--check | --yes | --help]

  (no option)  Set everything up. It asks before each download.
  --check      Report what is present and what is missing. Changes nothing.
  --yes        Answer yes to every question, for unattended use.
  --help       Show this message.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --check) MODE="check" ;;
    --yes|-y) ASSUME_YES=1 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown option: $arg"; usage; exit 2 ;;
  esac
done

# Work in the folder that holds pyproject.toml: the current one, else the script's.
if [ -f "$PWD/pyproject.toml" ]; then ROOT="$PWD"; else ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; fi
cd "$ROOT" || exit 1

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then G=$'\033[32m'; Y=$'\033[33m'; R=$'\033[31m'; B=$'\033[1m'; N=$'\033[0m'; else G=""; Y=""; R=""; B=""; N=""; fi
ok()      { echo "  ${G}ok${N}       $*"; }
missing() { echo "  ${Y}missing${N}  $*"; }
problem() { echo "  ${R}problem${N}  $*"; }
note()    { echo "           $*"; }
section() { echo; echo "${B}$*${N}"; }
have()    { command -v "$1" >/dev/null 2>&1; }

ask() {  # ask "question": yes with --yes, no when nobody can answer
  [ "$ASSUME_YES" -eq 1 ] && return 0
  [ -t 0 ] || return 1
  printf "           %s [y/N] " "$1"
  read -r reply
  case "$reply" in y|Y|yes|YES) return 0 ;; *) return 1 ;; esac
}

python_ok() { "$1" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)' >/dev/null 2>&1; }

find_python() {
  for candidate in python3.13 python3.12 python3 python; do
    if have "$candidate" && python_ok "$candidate"; then echo "$candidate"; return 0; fi
  done
  return 1
}

TODO=()   # what is still needed, repeated at the end

# ---------------------------------------------------------------- Python
section "1. Python and the project's environment"
PY=""
if [ -x .venv/bin/python ] && python_ok .venv/bin/python; then
  PY=".venv/bin/python"
  ok "Python environment is set up (.venv, $($PY -c 'import platform; print(platform.python_version())'))"
else
  SYSTEM_PY="$(find_python || true)"
  if [ -z "$SYSTEM_PY" ]; then
    problem "Python 3.12 or newer was not found."
    note "Install it first: https://www.python.org/downloads/ (or 'brew install python@3.13' on a Mac)."
    missing "Python environment: not set up"
    TODO+=("Install Python 3.12 or newer, then run ./setup.sh again.")
  elif [ "$MODE" = "check" ]; then
    ok "Python found: $SYSTEM_PY"
    missing "Python environment: not set up (./setup.sh will create .venv and install the dependencies)"
    TODO+=("Run ./setup.sh to create the Python environment.")
  else
    ok "Python found: $SYSTEM_PY"
    echo "           Creating .venv and installing the core dependencies (a few megabytes)..."
    LOG="$(mktemp)"
    if "$SYSTEM_PY" -m venv .venv >"$LOG" 2>&1 && .venv/bin/python -m pip install -q --upgrade pip >>"$LOG" 2>&1 \
       && .venv/bin/python -m pip install -q -e ".[dev]" >>"$LOG" 2>&1; then
      PY=".venv/bin/python"
      ok "Python environment is set up"
    else
      cat "$LOG"
      problem "Could not create the environment. The error is shown above."
      TODO+=("Fix the Python environment error above, then run ./setup.sh again.")
    fi
  fi
fi

# ---------------------------------------------------------------- PyTorch
section "2. PyTorch, for the exercises in sessions 2 to 5"
if [ -n "$PY" ] && "$PY" -c 'import torch' >/dev/null 2>&1; then
  ok "PyTorch is installed"
elif [ -z "$PY" ]; then
  missing "PyTorch: needs the Python environment first"
elif [ "$MODE" = "check" ]; then
  missing "PyTorch: not installed (about 80 MB; session 1 works without it)"
  TODO+=("Install PyTorch with: make setup-lessons")
elif ask "Download and install PyTorch now (about 80 MB)?"; then
  if "$PY" -m pip install -q -e ".[dev,lessons]" 2>/dev/null; then ok "PyTorch is installed"; else problem "PyTorch did not install. Run 'make setup-lessons' to see why."; TODO+=("Install PyTorch with: make setup-lessons"); fi
else
  missing "PyTorch: skipped. Session 1 works without it."
  TODO+=("Before session 2, install PyTorch with: make setup-lessons")
fi

# ---------------------------------------------------------------- data
section "3. Incident data for the service desk"
if [ -f data/timetravel.db ]; then
  ok "Incident data is generated (data/timetravel.db)"
elif [ -z "$PY" ] || [ "$MODE" = "check" ]; then
  missing "Incident data: not generated"
  [ -n "$PY" ] && TODO+=("Generate the incidents with: make data")
else
  echo "           Generating 500 incidents (a few seconds, no download)..."
  if "$PY" -m servicedesk.generate >/dev/null; then ok "Incident data is generated"; else problem "Could not generate the data."; TODO+=("Generate the incidents with: make data"); fi
fi

# ---------------------------------------------------------------- Ollama
section "4. A local model, through Ollama"
OLLAMA_RUNNING=0
if ! have ollama; then
  missing "Ollama: not installed"
  note "Without it, Buddy still answers questions about your progress, but cannot explain"
  note "lessons, give hints or quiz you, and session 5's experiments will not run."
  if [ "$MODE" = "setup" ] && have brew && ask "Install Ollama now with Homebrew?"; then
    if brew install ollama; then ok "Ollama is installed"; else problem "Homebrew could not install Ollama."; fi
  fi
  if ! have ollama; then
    note "Get it from https://ollama.com/download and run ./setup.sh again."
    TODO+=("Install Ollama from https://ollama.com/download")
  fi
fi
if have ollama; then
  ok "Ollama is installed"
  if have curl; then curl -s -m 3 -o /dev/null http://localhost:11434/api/tags && OLLAMA_RUNNING=1
  else ollama list >/dev/null 2>&1 && OLLAMA_RUNNING=1; fi
  if [ "$OLLAMA_RUNNING" -eq 1 ]; then
    ok "Ollama is running"
  else
    missing "Ollama is installed but not running"
    note "Start it with: ollama serve   (or open the Ollama app)"
    TODO+=("Start Ollama with: ollama serve")
  fi
  MODELS="$(ollama list 2>/dev/null || true)"
  if printf '%s\n' "$MODELS" | grep -q "^$MODEL"; then
    ok "$MODEL is downloaded"
  elif [ "$OLLAMA_RUNNING" -eq 1 ] && [ "$MODE" = "setup" ] && ask "Download the model $MODEL now (about 2.5 GB)?"; then
    if ollama pull "$MODEL"; then ok "$MODEL is downloaded"; else problem "The model did not download."; TODO+=("Download the model with: ollama pull $MODEL"); fi
  else
    missing "$MODEL is not downloaded (about 2.5 GB)"
    TODO+=("Download the model with: ollama pull $MODEL")
  fi
fi

# ---------------------------------------------------------------- Docker
section "5. Docker (optional)"
if have docker; then ok "Docker is installed (optional: 'make up' runs both apps in containers)"
else ok "Docker: not installed. It is optional; 'make serve' runs both apps without it."; fi

# ---------------------------------------------------------------- summary
section "Summary"
if [ "${#TODO[@]}" -eq 0 ]; then
  echo "  Everything is ready. Start both apps with:  make serve"
  echo "  Course app   http://localhost:8000"
  echo "  Service desk http://localhost:8080"
else
  echo "  Still to do:"
  for item in "${TODO[@]}"; do echo "   - $item"; done
  [ -n "$PY" ] && [ -f data/timetravel.db ] && echo "  You can already start the apps with:  make serve"
fi
[ "$MODE" = "check" ] && echo "  (--check only reports; nothing was changed.)"
exit 0
