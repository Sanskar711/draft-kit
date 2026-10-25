"""Run the test suite so CI always gets a log, even when something hangs.

A job killed by its own timeout-minutes is force-terminated after GitHub's
grace period and its log is discarded, so a hang leaves nothing to debug.
Bounding the run here instead keeps the step well inside the job timeout:
the step fails, the job finishes normally and the log survives.
"""
import os
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT = int(os.environ.get("DRAFT_KIT_PYTEST_TIMEOUT", "420"))


def terminate(process):
    """Kill the whole tree. An orphan holding stdout keeps the step open."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(process.pid)],
                       capture_output=True)
    else:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            process.kill()


def main():
    command = [sys.executable, "-X", "faulthandler", "-m", "pytest", *sys.argv[1:]]
    print("ci_pytest: " + " ".join(command) + f" (limit {LIMIT}s)", flush=True)
    # Unbuffered so output already written survives a kill, and a new process
    # group so no test subprocess outlives the run holding the log pipe open.
    process = subprocess.Popen(
        command, cwd=ROOT,
        env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONUTF8": "1"},
        **({} if sys.platform == "win32" else {"start_new_session": True}),
    )
    try:
        return process.wait(timeout=LIMIT)
    except subprocess.TimeoutExpired:
        terminate(process)
        process.wait()
        print(
            f"\nci_pytest: no result after {LIMIT}s, so the suite is hung.\n"
            "ci_pytest: the last test named above is where it stopped; nothing\n"
            "ci_pytest: named means collection or import never finished.",
            flush=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
