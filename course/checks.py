"""Runs one lesson test in a separate process, so broken or endless learner
code cannot take the server down."""
import subprocess
import sys

DEFAULT_TIMEOUT = 60
MAX_OUTPUT = 4000


def run_check(test_node: str, cwd: str, timeout: int | None = None) -> tuple[bool, str]:
    timeout = timeout or DEFAULT_TIMEOUT
    cmd = [sys.executable, "-m", "pytest", *test_node.split(), "-q", "--no-header", "-x", "--color=no", "-p", "no:cacheprovider"]
    try:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"Timed out after {timeout} seconds. Check for a loop that never ends."
    output = (done.stdout + done.stderr).strip()[-MAX_OUTPUT:]
    if "No module named 'torch'" in output:
        output = ("This exercise needs PyTorch. Run `make setup-lessons` in the project folder, then try again.\n\n"
                  + output)
    return done.returncode == 0, output
