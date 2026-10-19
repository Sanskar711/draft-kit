"""Cross-platform source launcher. Only Python's standard library is required."""
import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def prepare_environment(root: Path) -> Path:
    environment = root / ".venv"
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.exists():
        print("Creating the local Python environment...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(environment)], check=True)
    digest = hashlib.sha256((root / "requirements.txt").read_bytes()).hexdigest()
    marker = environment / "composer-requirements-hash"
    if not marker.exists() or marker.read_text().strip() != digest:
        print("Installing companion dependencies. This needs internet access...", flush=True)
        subprocess.run([str(python), "-m", "pip", "install", "--upgrade", "pip"], check=True, cwd=root)
        subprocess.run([str(python), "-m", "pip", "install", "-r", "requirements.txt"], check=True, cwd=root)
        marker.write_text(digest)
    return python


def main():
    parser = argparse.ArgumentParser(description="Set up and start the draft-kit local companion.")
    parser.add_argument("--demo", action="store_true", help="Try template drafts without ChatGPT sign-in")
    parser.add_argument("--port", type=int, default=1455, help="Local port (default: 1455)")
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.error("Install Python 3.11 or later. Python 3.12 is recommended.")
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a port between 1024 and 65535.")
    try:
        python = prepare_environment(ROOT)
    except subprocess.CalledProcessError:
        raise SystemExit("Setup failed. See the error above and README.md Troubleshooting. Run this command again after fixing it.") from None
    command = [str(python), "-m", "companion", "--port", str(args.port)]
    if args.demo:
        command.append("--demo")
    process = subprocess.Popen(command, cwd=ROOT, env={**os.environ, "PYTHONUTF8": "1"})
    try:
        return process.wait()
    except KeyboardInterrupt:
        # Ctrl+C reaches both processes in this terminal's process group.
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
