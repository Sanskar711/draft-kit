"""Place the beta extension in a stable, user-owned folder."""
import json
import shutil
import sys
from pathlib import Path


def revealable_extension(data_dir):
    source = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[1])) / "extension" / "dist"
    destination = data_dir / "extension"
    current = json.loads((source / "manifest.json").read_text())["version"]
    try:
        previous = json.loads((destination / "manifest.json").read_text()).get("version")
    except (OSError, ValueError):
        previous = None
    if previous != current:
        shutil.copytree(source, destination, dirs_exist_ok=True)
    return destination
