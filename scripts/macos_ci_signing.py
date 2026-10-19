"""Provision temporary CI signing credentials without printing secrets."""
import argparse
import base64
import json
import os
import secrets
import shlex
import subprocess
import sys
from pathlib import Path


def run(arguments):
    # Never log command arguments: some native tools require a password argument.
    result = subprocess.run([str(argument) for argument in arguments], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{Path(str(arguments[0])).name} failed during signing setup; verify the configured certificates and credentials.")
    return result.stdout


def locations():
    directory = Path(os.environ["RUNNER_TEMP"])
    return directory / "draft-kit-signing.keychain-db", directory / "draft-kit-keychains.json"


def cleanup():
    keychain, previous = locations()
    if previous.exists():
        run(["security", "list-keychains", "-d", "user", "-s", *json.loads(previous.read_text())])
        previous.unlink()
    if keychain.exists():
        run(["security", "delete-keychain", keychain])


def setup():
    required = ["MACOS_SIGNING_P12_BASE64", "MACOS_SIGNING_P12_PASSWORD", "APPLE_ID", "APPLE_APP_PASSWORD", "APPLE_TEAM_ID", "DRAFT_KIT_APP_SIGNING_IDENTITY", "DRAFT_KIT_INSTALLER_SIGNING_IDENTITY"]
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("Missing GitHub Actions secrets: " + ", ".join(missing))
    keychain, previous = locations()
    if keychain.exists() or previous.exists():
        raise RuntimeError("A signing setup already exists on this runner.")
    os.umask(0o077)
    previous.write_text(json.dumps(shlex.split(run(["security", "list-keychains", "-d", "user"]))))
    password = secrets.token_urlsafe(32)
    certificate = keychain.with_suffix(".p12")
    try:
        certificate.write_bytes(base64.b64decode("".join(os.environ["MACOS_SIGNING_P12_BASE64"].split()), validate=True))
        run(["security", "create-keychain", "-p", password, keychain])
        run(["security", "set-keychain-settings", "-lut", "21600", keychain])
        run(["security", "unlock-keychain", "-p", password, keychain])
        run(["security", "import", certificate, "-P", os.environ["MACOS_SIGNING_P12_PASSWORD"], "-t", "cert", "-f", "pkcs12", "-k", keychain, "-T", "/usr/bin/codesign", "-T", "/usr/bin/productsign", "-T", "/usr/bin/pkgbuild"])
        run(["security", "set-key-partition-list", "-S", "apple-tool:,apple:,codesign:", "-s", "-k", password, keychain])
        run(["security", "list-keychains", "-d", "user", "-s", keychain, *json.loads(previous.read_text())])
        run(["xcrun", "notarytool", "store-credentials", "draft-kit-ci", "--apple-id", os.environ["APPLE_ID"], "--team-id", os.environ["APPLE_TEAM_ID"], "--password", os.environ["APPLE_APP_PASSWORD"], "--keychain", keychain])
        with Path(os.environ["GITHUB_ENV"]).open("a") as environment:
            environment.write(f"DRAFT_KIT_NOTARY_PROFILE=draft-kit-ci\nDRAFT_KIT_NOTARY_KEYCHAIN={keychain}\n")
    finally:
        certificate.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("setup", "cleanup"))
    args = parser.parse_args()
    if sys.platform != "darwin" or not os.environ.get("GITHUB_ACTIONS") or not os.environ.get("RUNNER_TEMP"):
        parser.error("This helper is only for a macOS GitHub Actions runner.")
    try:
        setup() if args.action == "setup" else cleanup()
    except Exception as error:
        print(str(error) if isinstance(error, RuntimeError) else "Signing setup failed. Check the configured GitHub secrets.", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
