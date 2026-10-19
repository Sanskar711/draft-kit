import base64
import json
import os
import subprocess
from types import SimpleNamespace

import pytest

from scripts import macos_ci_signing as signing
from scripts import build_macos as builder


def test_signing_setup_rejects_missing_secrets_before_native_calls(monkeypatch):
    for name in ("MACOS_SIGNING_P12_BASE64", "MACOS_SIGNING_P12_PASSWORD", "APPLE_ID", "APPLE_APP_PASSWORD", "APPLE_TEAM_ID", "DRAFT_KIT_APP_SIGNING_IDENTITY", "DRAFT_KIT_INSTALLER_SIGNING_IDENTITY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(signing, "run", lambda args: pytest.fail("No keychain operation should run without required secrets."))
    with pytest.raises(RuntimeError, match="Missing GitHub Actions secrets"):
        signing.setup()


def test_signing_failure_does_not_expose_native_output_or_password(monkeypatch):
    password = "test-private-password"
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=1, stdout=password, stderr=password))
    with pytest.raises(RuntimeError) as failure:
        signing.run(["security", "import", "certificate.p12", "-P", password])
    assert password not in str(failure.value)
    assert "security failed" in str(failure.value)


def test_ci_setup_and_cleanup_preserve_keychain_list_and_delete_certificate(monkeypatch, tmp_path):
    values = {
        "RUNNER_TEMP": str(tmp_path), "GITHUB_ENV": str(tmp_path / "environment"),
        "MACOS_SIGNING_P12_BASE64": base64.encodebytes(b"simulated signing identity").decode(),
        "MACOS_SIGNING_P12_PASSWORD": "test-password", "APPLE_ID": "test@example.invalid",
        "APPLE_APP_PASSWORD": "test-notary-password", "APPLE_TEAM_ID": "TESTTEAM",
        "DRAFT_KIT_APP_SIGNING_IDENTITY": "Developer ID Application: Test",
        "DRAFT_KIT_INSTALLER_SIGNING_IDENTITY": "Developer ID Installer: Test",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    operations = []
    keychain, previous = signing.locations()
    original = '/Users/runner/Library/Keychains/login.keychain-db'
    def native(arguments):
        arguments = [str(arg) for arg in arguments]
        operations.append(arguments)
        if arguments == ["security", "list-keychains", "-d", "user"]:
            return f'"{original}"\n'
        if arguments[1] == "create-keychain":
            keychain.touch()
        elif arguments[1] == "delete-keychain":
            keychain.unlink()
        return ""
    monkeypatch.setattr(signing, "run", native)
    old_mask = os.umask(0o077)
    try:
        signing.setup()
        assert not keychain.with_suffix('.p12').exists()
        if os.name != "nt":
            assert previous.stat().st_mode & 0o777 == 0o600
        assert "DRAFT_KIT_NOTARY_KEYCHAIN=" in (tmp_path / "environment").read_text()
        signing.cleanup()
    finally:
        os.umask(old_mask)
    assert ["security", "list-keychains", "-d", "user", "-s", original] in operations
    assert not keychain.exists() and not previous.exists()


def test_intel_crypto_environment_requires_static_archives_and_overrides_dynamic_flag(monkeypatch, tmp_path):
    for relative in ("include/openssl/opensslv.h", "lib/libssl.a", "lib/libcrypto.a"):
        file = tmp_path / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.touch()
    monkeypatch.setenv("DRAFT_KIT_OPENSSL_DIR", str(tmp_path))
    monkeypatch.setenv("OPENSSL_STATIC", "0")
    monkeypatch.setattr(builder.shutil, "which", lambda name: "/tools/" + name)
    environment = builder.crypto_build_environment("x86_64")
    assert environment["OPENSSL_STATIC"] == "1"
    assert environment["OPENSSL_DIR"] == str(tmp_path.resolve())
    assert environment["OPENSSL_NO_VENDOR"] == "1"
    assert environment["MACOSX_DEPLOYMENT_TARGET"] == "13.0"


def test_intel_crypto_environment_stops_before_install_with_incomplete_openssl(monkeypatch, tmp_path):
    monkeypatch.setenv("DRAFT_KIT_OPENSSL_DIR", str(tmp_path))
    monkeypatch.setattr(builder.shutil, "which", lambda name: "/tools/" + name)
    with pytest.raises(RuntimeError, match="static libraries/headers are missing"):
        builder.crypto_build_environment("x86_64")


def test_crypto_linkage_accepts_system_dependencies_without_openssl(monkeypatch, tmp_path):
    output = f"{tmp_path}/_rust.abi3.so:\n\t/usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1345.100.2)\n"
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: output)
    assert builder.check_static_crypto(tmp_path / "_rust.abi3.so") == ["/usr/lib/libSystem.B.dylib"]


@pytest.mark.parametrize("library", ["@rpath/libssl.3.dylib", "/usr/local/opt/openssl@3/lib/libcrypto.3.dylib"])
def test_crypto_linkage_rejects_each_dynamic_openssl_library(monkeypatch, tmp_path, library):
    output = f"{tmp_path}/_rust.abi3.so:\n\t{library} (compatibility version 3.0.0, current version 3.6.0)\n"
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: output)
    with pytest.raises(RuntimeError, match="still depends on dynamic OpenSSL"):
        builder.check_static_crypto(tmp_path / "_rust.abi3.so")


def test_crypto_linkage_does_not_assume_success_from_empty_output(monkeypatch, tmp_path):
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: "")
    with pytest.raises(RuntimeError, match="Could not inspect"):
        builder.check_static_crypto(tmp_path / "_rust.abi3.so")


@pytest.mark.parametrize("arch,selection", [("x86_64", "--no-binary=cryptography"), ("arm64", "--only-binary=cryptography")])
def test_crypto_install_repairs_reused_venv_bypasses_cache_and_checks_result(monkeypatch, tmp_path, arch, selection):
    (tmp_path / "requirements.txt").write_text("cryptography==50.0.2\n")
    monkeypatch.setattr(builder, "ROOT", tmp_path)
    environment = {"MACOSX_DEPLOYMENT_TARGET": "13.0", "OPENSSL_STATIC": "1"}
    monkeypatch.setattr(builder, "crypto_build_environment", lambda actual_arch: environment)
    commands = []
    monkeypatch.setattr(builder, "run", lambda args, **kwargs: commands.append((list(map(str, args)), kwargs)))
    binary = tmp_path / "_rust.abi3.so"
    probe = {"version": "50.0.2", "binary": str(binary), "openssl": "OpenSSL 3.6.0", "python_openssl": "OpenSSL 3.0.0"}
    monkeypatch.setattr(builder.subprocess, "check_output", lambda *args, **kwargs: json.dumps(probe))
    inspected = []
    def inspect(path):
        inspected.append(path)
        return ["/usr/lib/libSystem.B.dylib"]
    monkeypatch.setattr(builder, "check_static_crypto", inspect)
    result_environment, result = builder.install_build_dependencies(tmp_path / "python", arch)
    first, options = commands[0]
    assert all(flag in first for flag in ("--force-reinstall", "--no-deps", "--no-cache-dir", selection, "cryptography==50.0.2"))
    assert options["env"] == result_environment == environment
    assert inspected == [binary] and result["architecture"] == arch
    assert len(commands) == 2
