"""Create a GitHub-ready source ZIP using an explicit source-file allowlist."""
import argparse
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    "README.md", "LICENSE", "PRIVACY.md", "CONTRIBUTING.md", "CHANGELOG.md", "THIRD_PARTY_NOTICES.txt",
    ".gitignore", ".gitattributes", "package.json", "package-lock.json", "tsconfig.json",
    "requirements.txt", "requirements-dev.txt", "requirements-desktop.txt", "requirements-build.txt",
    "requirements-windows.txt", "requirements-windows-build.txt", "Start draft-kit.cmd",
    "Start Offline Demo.cmd", "Start draft-kit.command", "Start Offline Demo.command",
}
SUFFIXES = {
    ".github": {".yml", ".yaml"}, "companion": {".py"},
    "desktop": {".py", ".spec", ".plist", ".iss", ".svg", ".png"},
    "extension": {".ts", ".tsx", ".js", ".json", ".css", ".html", ".svg", ".png", ".txt"},
    "scripts": {".py", ".mjs", ".sh"}, "tests": {".py", ".mjs", ".json", ".html"},
    "docs": {".md"},
}
BLOCKED_PARTS = {"__pycache__", ".test-state", "node_modules", ".venv", ".git", "build", "release", ".pytest_cache"}


def source_files(root: Path):
    required = ["README.md", "LICENSE", "companion/__main__.py", "extension/dist/manifest.json"]
    for name in required:
        if not (root / name).is_file():
            raise RuntimeError("Missing required source file: " + name)
    for name in sorted(ROOT_FILES):
        path = root / name
        if path.is_file() and not path.is_symlink():
            yield path
    for folder, suffixes in sorted(SUFFIXES.items()):
        for path in sorted((root / folder).rglob("*")):
            relative = path.relative_to(root)
            if any(part in BLOCKED_PARTS for part in relative.parts):
                continue
            # Do not follow an aliased path to a file outside the repository.
            if any(parent.is_symlink() for parent in [path, *path.parents] if parent != root and root in parent.parents):
                continue
            if path.is_file() and (path.suffix in suffixes or path.name == "LICENSE"):
                if path.name not in {"build-icon.icns", "build-licenses.txt"}:
                    yield path


def package(root: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source_files(root):
            archive.write(path, "draft-kit/" + path.relative_to(root).as_posix())
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
    destination = args.output or ROOT / "release" / f"draft-kit-v{version}-source.zip"
    print(package(ROOT, destination).resolve())


if __name__ == "__main__":
    main()
