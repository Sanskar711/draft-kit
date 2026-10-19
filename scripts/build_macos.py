"""Maintainer build: bundles Python, tests the runtime, and creates a macOS PKG."""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(arguments, **kwargs):
    subprocess.run([str(argument) for argument in arguments], check=True, cwd=ROOT, **kwargs)


def crypto_build_environment(arch):
    environment = {**os.environ, "MACOSX_DEPLOYMENT_TARGET": "13.0"}
    if arch == "x86_64":
        # Recent cryptography releases have no Intel Mac wheel. Its default
        # source build links Homebrew's libssl dynamically, which can collide
        # with Python's older library of the same name in a frozen bundle.
        for tool in ("cargo", "rustc"):
            if not shutil.which(tool):
                raise RuntimeError("The Intel maintainer build needs Rust. Install Rust with rustup, then retry. End users do not need Rust.")
        prefix = os.environ.get("DRAFT_KIT_OPENSSL_DIR")
        if not prefix:
            if not shutil.which("brew"):
                raise RuntimeError("The Intel maintainer build needs Homebrew openssl@3 or DRAFT_KIT_OPENSSL_DIR pointing to its headers and static libraries.")
            prefix = subprocess.check_output(["brew", "--prefix", "openssl@3"], text=True).strip()
        openssl = Path(prefix).expanduser().resolve()
        for relative in ("include/openssl/opensslv.h", "lib/libssl.a", "lib/libcrypto.a"):
            if not (openssl / relative).is_file():
                raise RuntimeError("OpenSSL static libraries/headers are missing. Run brew install openssl@3, or set DRAFT_KIT_OPENSSL_DIR to a complete installation.")
        environment.update(OPENSSL_STATIC="1", OPENSSL_DIR=str(openssl), OPENSSL_NO_VENDOR="1")
    return environment


def check_static_crypto(binary):
    output = subprocess.check_output(["otool", "-L", str(binary)], text=True)
    dependencies = []
    for line in output.splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if dependency:
            dependencies.append(dependency)
    dynamic = [dependency for dependency in dependencies if re.search(r"(?:^|/)(?:libssl|libcrypto)(?:\.|$)", dependency)]
    if dynamic:
        raise RuntimeError("cryptography still depends on dynamic OpenSSL: " + ", ".join(dynamic) + ". Stop the build; a static dependency is required for this installer.")
    if not dependencies:
        raise RuntimeError("Could not inspect cryptography's native dependencies. Stop the build rather than assuming static linkage.")
    return dependencies


def install_build_dependencies(python, arch):
    environment = crypto_build_environment(arch)
    # Reinstall only cryptography, then resolve the remaining requirements.
    # --no-cache-dir prevents reusing the earlier dynamically linked wheel;
    # --force-reinstall also repairs a reused build venv at the same version.
    pins = [line.strip() for line in (ROOT / "requirements.txt").read_text().splitlines() if line.strip().startswith("cryptography==")]
    if len(pins) != 1 or not re.fullmatch(r"cryptography==[0-9]+(?:\.[0-9]+)+", pins[0]):
        raise RuntimeError("The build requires one exact cryptography version pin in requirements.txt.")
    selection = "--no-binary=cryptography" if arch == "x86_64" else "--only-binary=cryptography"
    print("Installing cryptography with static OpenSSL for " + arch + "…", flush=True)
    run([python, "-m", "pip", "install", "--force-reinstall", "--no-deps", "--no-cache-dir", selection, pins[0]], env=environment)
    run([python, "-m", "pip", "install", "-r", ROOT / "requirements-build.txt"], env=environment)
    probe = "import json, ssl; import cryptography; import cryptography.hazmat.bindings._rust as rust; from cryptography.hazmat.backends.openssl.backend import backend; print(json.dumps({'version': cryptography.__version__, 'binary': rust.__file__, 'openssl': backend.openssl_version_text(), 'python_openssl': ssl.OPENSSL_VERSION}))"
    details = json.loads(subprocess.check_output([str(python), "-c", probe], text=True, cwd=ROOT, env=environment))
    details["dependencies"] = check_static_crypto(Path(details["binary"]))
    details["architecture"] = arch
    print("PASS cryptography static linkage: " + details["openssl"], flush=True)
    return environment, details


def main():
    parser = argparse.ArgumentParser(description="Build draft-kit for this Mac's CPU architecture.")
    parser.add_argument("--signed", action="store_true", help="Require Developer ID application and installer identities.")
    parser.add_argument("--notarize", action="store_true", help="Submit the signed PKG using a saved notarytool Keychain profile.")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Run this on macOS, or use the included macOS GitHub Actions workflow. Linux cannot build this Mac installer.")
    if sys.version_info < (3, 11):
        parser.error("The maintainer build needs Python 3.11+. End users will not need Python.")
    signed = args.signed or args.notarize
    application_identity = os.environ.get("DRAFT_KIT_APP_SIGNING_IDENTITY") or os.environ.get("COMPOSER_APP_SIGNING_IDENTITY")
    installer_identity = os.environ.get("DRAFT_KIT_INSTALLER_SIGNING_IDENTITY") or os.environ.get("COMPOSER_INSTALLER_SIGNING_IDENTITY")
    notary_profile = os.environ.get("DRAFT_KIT_NOTARY_PROFILE") or os.environ.get("COMPOSER_NOTARY_PROFILE")
    if signed and not all((application_identity, installer_identity)):
        parser.error("Set DRAFT_KIT_APP_SIGNING_IDENTITY and DRAFT_KIT_INSTALLER_SIGNING_IDENTITY to your installed Developer ID certificates.")
    if args.notarize and not notary_profile:
        parser.error("Set DRAFT_KIT_NOTARY_PROFILE to the saved notarytool Keychain profile.")
    for tool in ("pkgbuild", "sips", "iconutil", "otool"):
        if not shutil.which(tool):
            parser.error("Missing macOS build tool: " + tool)
    version = json.loads((ROOT / "extension/dist/manifest.json").read_text())["version"]
    arch = platform.machine()
    if arch not in ("arm64", "x86_64"):
        parser.error("Use an Apple Silicon or Intel Mac.")
    build = ROOT / "build" / "macos" / arch
    build.mkdir(parents=True, exist_ok=True)
    environment = build / "venv"
    if not (environment / "bin/python").exists():
        run([sys.executable, "-m", "venv", environment])
    python = environment / "bin/python"
    try:
        env, crypto = install_build_dependencies(python, arch)
    except RuntimeError as error:
        parser.error(str(error))
    (build / "cryptography-linkage.json").write_text(json.dumps(crypto, indent=2) + "\n")
    run([python, "-c", "import AppKit; import Foundation; import ServiceManagement; import desktop.menubar; import pypdf; import keyring"], env=env)
    run([python, ROOT / "scripts/collect_licenses.py", ROOT / "desktop/build-licenses.txt"])
    icons = build / "app.iconset"
    icons.mkdir(exist_ok=True)
    for size in (16, 32, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            run(["sips", "-z", size * scale, size * scale, ROOT / "extension/icons/1024.png", "--out", icons / f"icon_{size}x{size}{suffix}.png"], stdout=subprocess.DEVNULL)
    run(["iconutil", "-c", "icns", icons, "-o", ROOT / "desktop/build-icon.icns"])
    dist = build / "dist"
    if not signed:
        env.pop("COMPOSER_APP_SIGNING_IDENTITY", None)
        env.pop("DRAFT_KIT_APP_SIGNING_IDENTITY", None)
    elif application_identity:
        env["DRAFT_KIT_APP_SIGNING_IDENTITY"] = application_identity
    run([python, "-m", "PyInstaller", "--noconfirm", "--clean", "--distpath", dist,
         "--workpath", build / "pyinstaller", ROOT / "desktop/DraftKit.spec"], env=env)
    app = dist / "draft-kit.app"
    bundled_crypto = app / "Contents/Frameworks/cryptography/hazmat/bindings" / Path(crypto["binary"]).name
    try:
        check_static_crypto(bundled_crypto)
    except RuntimeError as error:
        parser.error(str(error))
    run([app / "Contents/MacOS/draft-kit", "--self-test"], env=env)
    run(["codesign", "--verify", "--deep", "--strict", app])
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    flavor = "notarized" if args.notarize else "signed" if signed else "unsigned-beta"
    installer = release / f"draft-kit-{version}-macos-{arch}-{flavor}.pkg"
    command = ["pkgbuild", "--component", app, "--install-location", "/Applications", "--identifier", "com.careercomposer.desktop", "--version", version]
    if signed:
        command += ["--sign", installer_identity]
    run([*command, installer])
    if args.notarize:
        notarize_command = ["xcrun", "notarytool", "submit", installer, "--keychain-profile", notary_profile, "--wait"]
        if os.environ.get("DRAFT_KIT_NOTARY_KEYCHAIN"):
            notarize_command += ["--keychain", os.environ["DRAFT_KIT_NOTARY_KEYCHAIN"]]
        run(notarize_command)
        run(["xcrun", "stapler", "staple", installer])
        run(["xcrun", "stapler", "validate", installer])
        run(["spctl", "--assess", "--type", "install", installer])
    extension = release / f"draft-kit-extension-{version}.zip"
    with zipfile.ZipFile(extension, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((ROOT / "extension/dist").rglob("*")):
            if path.is_file():
                archive.write(path, str(path.relative_to(ROOT / "extension/dist")))
    for artifact in (installer, extension):
        artifact.with_suffix(artifact.suffix + ".sha256").write_text(hashlib.sha256(artifact.read_bytes()).hexdigest() + "  " + artifact.name + "\n")
    shutil.copyfile(ROOT / "docs/INSTALLING.md", release / "INSTALL.md")
    print("\nBuild complete: " + str(installer))
    print("Extension package: " + str(extension))
    print("Test install and live account sign-in on a clean Mac before distributing.")
    if not args.notarize:
        print("This package is not notarized. It is for maintainer/beta validation, not a public audience launch.")


if __name__ == "__main__":
    main()
