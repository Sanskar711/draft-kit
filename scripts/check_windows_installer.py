"""CI install/runtime/uninstall check; operates only in a fresh temporary folder."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    if sys.platform != "win32":
        raise SystemExit("This installer check requires Windows.")
    installer = Path(sys.argv[1]).resolve()
    with tempfile.TemporaryDirectory(prefix="draft-kit-installer-") as directory:
        root = Path(directory)
        destination = root / "Installed App"
        report = root / "self-test.json"
        env = {**os.environ, "CAREER_COMPOSER_DATA_DIR": str(root / "data"), "CAREER_COMPOSER_KEY_DIR": str(root / "keys")}
        subprocess.run([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", f"/DIR={destination}", f"/LOG={root / 'install.log'}"], check=True, timeout=120)
        try:
            assert (destination / "draft-kit-worker.exe").is_file()
            subprocess.run([str(destination / "draft-kit.exe"), "--self-test", "--self-test-report", str(report)], check=True, timeout=90, env=env)
            assert json.loads(report.read_text(encoding="utf-8"))["ok"] is True
        finally:
            subprocess.run([str(destination / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"], check=True, timeout=120)
        assert not (destination / "draft-kit.exe").exists()
    print("PASS per-user installer, installed frozen runtime/PDF worker, and uninstaller")


if __name__ == "__main__":
    main()
