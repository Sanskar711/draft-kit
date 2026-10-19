"""Collect installed dependency license text for the desktop bundle."""
import importlib.metadata
import sys
from pathlib import Path


def collect(destination: Path):
    sections = ["draft-kit desktop dependencies\nPython runtime: https://docs.python.org/3/license.html\n"]
    for distribution in sorted(importlib.metadata.distributions(), key=lambda item: item.metadata.get("Name", "")):
        sections.append("\n" + distribution.metadata.get("Name", "Unknown") + " " + distribution.version + "\n")
        texts = []
        for file in distribution.files or []:
            if file.name.lower().startswith(("license", "licence", "copying", "notice")):
                path = distribution.locate_file(file)
                if path.is_file():
                    texts.append(path.read_text(encoding="utf-8", errors="replace"))
        sections.extend(texts or [distribution.metadata.get("License", "See package metadata for license terms.")])
    for directory in [Path(sys.base_prefix), Path(sys.base_prefix) / "lib", Path(sys.base_prefix) / "Resources"]:
        for name in ["LICENSE.txt", "LICENSE", "license.terms"]:
            path = directory / name
            if path.is_file():
                sections.append(path.read_text(encoding="utf-8", errors="replace"))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(sections), encoding="utf-8")


if __name__ == "__main__":
    collect(Path(sys.argv[1]))
