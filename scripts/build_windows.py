"""Build a self-contained x64 Windows tray app and per-user Inno Setup installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import sysconfig
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, **kwargs):
    subprocess.run([str(argument) for argument in arguments], check=True, cwd=ROOT, **kwargs)


def compiler_path():
    configured = os.environ.get("DRAFT_KIT_ISCC")
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise RuntimeError("DRAFT_KIT_ISCC must point to ISCC.exe.")
        return path
    found = shutil.which("ISCC.exe")
    if found:
        return Path(found)
    for variable in ("ProgramFiles(x86)", "ProgramFiles"):
        base = os.environ.get(variable)
        if base:
            candidates = sorted(Path(base).glob("Inno Setup*/ISCC.exe"), reverse=True)
            if candidates:
                return candidates[0]
    raise RuntimeError("Install Inno Setup, or set DRAFT_KIT_ISCC to its ISCC.exe path.")


def validate_host():
    if sys.platform != "win32":
        raise RuntimeError("Build on Windows, or run Actions > Build Windows installer in GitHub. A Windows executable cannot be frozen on this host.")
    if sys.version_info < (3, 11) or struct.calcsize("P") != 8 or sysconfig.get_platform() != "win-amd64":
        raise RuntimeError("Use 64-bit x64 Python 3.11 or newer. Python 3.12 is recommended.")


def verify_runtime(executable: Path, report: Path):
    report.unlink(missing_ok=True)
    run([executable, "--self-test", "--self-test-report", report], timeout=90)
    if not report.exists() or json.loads(report.read_text(encoding="utf-8")).get("ok") is not True:
        raise RuntimeError("The bundled Windows self-test did not report success. No installer will be produced.")


def package_extension(release: Path, version: str):
    output = release / f"draft-kit-extension-{version}.zip"
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "extension/dist").rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(ROOT / "extension/dist").as_posix())
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        validate_host()
        compiler = compiler_path()
    except RuntimeError as error:
        parser.error(str(error))
    build = ROOT / "build/windows"
    build.mkdir(parents=True, exist_ok=True)
    environment = build / "venv"
    python = environment / "Scripts/python.exe"
    if not python.exists():
        run([sys.executable, "-m", "venv", environment])
    run([python, "-m", "pip", "install", "--upgrade", "pip"])
    run([python, "-m", "pip", "install", "-r", ROOT / "requirements-windows-build.txt"])
    run([python, "-c", "from PIL import Image; import sys; image=Image.open(sys.argv[1]); image.save(sys.argv[2], format='ICO', sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])", ROOT / "extension/icons/1024.png", build / "draft-kit.ico"])
    run([python, ROOT / "scripts/collect_licenses.py", build / "licenses.txt"])
    dist = build / "dist"
    run([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", dist,
         "--workpath", build / "pyinstaller", ROOT / "desktop/DraftKitWindows.spec"])
    bundle = dist / "draft-kit"
    if not (bundle / "draft-kit-worker.exe").is_file():
        raise RuntimeError("The bundled resume worker is missing.")
    verify_runtime(bundle / "draft-kit.exe", build / "self-test.json")
    version = json.loads((ROOT / "extension/dist/manifest.json").read_text(encoding="utf-8"))["version"]
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    installer = release / f"draft-kit-{version}-windows-x64-setup-unsigned-beta.exe"
    # A failed retry must not leave an older installer looking like fresh output.
    installer.unlink(missing_ok=True)
    run([compiler, f"/DAppVersion={version}", f"/DSourceRoot={ROOT}", f"/DBundleDir={bundle}",
         f"/DReleaseDir={release}", ROOT / "desktop/windows/installer.iss"])
    if not installer.is_file():
        raise RuntimeError("Inno Setup did not create the expected installer.")
    extension = package_extension(release, version)
    for artifact in (installer, extension):
        artifact.with_suffix(artifact.suffix + ".sha256").write_text(hashlib.sha256(artifact.read_bytes()).hexdigest() + "  " + artifact.name + "\n", encoding="utf-8")
    shutil.copyfile(ROOT / "docs/INSTALLING.md", release / "INSTALL.md")
    print("Installer: " + str(installer))
    print("Unsigned beta: validate on a clean Windows account before sharing. Sign for wider distribution.")


if __name__ == "__main__":
    main()
