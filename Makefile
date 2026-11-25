PY := .venv/bin/python

.PHONY: check setup setup-lessons data desk course serve up down test lint

# Report what is installed and what is missing, without changing anything
check:
	./setup.sh --check

setup:
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -e ".[dev]"

# PyTorch for the exercises in sessions 2 to 5 (about 80 MB)
setup-lessons:
	$(PY) -m pip install -q -e ".[dev,lessons]"

data:
	$(PY) -m servicedesk.generate

# The service desk (incident management tool) on http://localhost:8080
desk:
	$(PY) -m uvicorn servicedesk.app:app --port 8080

# The course app on http://localhost:8000
course:
	$(PY) -m uvicorn course.app:app --port 8000

# Both apps, each as its own process. Ctrl-C stops both.
serve:
	@trap "kill 0" INT TERM EXIT; $(PY) -m uvicorn servicedesk.app:app --port 8080 & $(PY) -m uvicorn course.app:app --port 8000 & wait

# Both apps as two containers.
up:
	docker compose up --build

down:
	docker compose down

test:
	$(PY) -m pytest -q

# The same lint checks CI runs: Python, YAML, then Markdown (needs Node for npx)
lint:
	$(PY) -m ruff check .
	$(PY) -m yamllint .
	npx --yes markdownlint-cli@0.50.1 "**/*.md"
