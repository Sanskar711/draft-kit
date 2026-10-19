"""Portability regressions: locks, OS storage, and failed/repeated setup."""
import os
from pathlib import Path
import subprocess
import sys

import keyring
import pytest

from companion.process_lock import AlreadyRunning, ProcessLock
from companion import storage
from scripts import start

ROOT = Path(__file__).resolve().parents[1]


def test_lock_excludes_another_process_and_releases_after_close(tmp_path):
    path = tmp_path / "process.lock"
    probe = '''
import sys
from pathlib import Path
from companion.process_lock import AlreadyRunning, ProcessLock
try:
    guard = ProcessLock(Path(sys.argv[1]))
except AlreadyRunning:
    print("held")
else:
    guard.close()
    print("available")
'''
    def attempt():
        result = subprocess.run([sys.executable, "-c", probe, str(path)], cwd=ROOT,
                                capture_output=True, text=True, timeout=15, check=True)
        return result.stdout.strip()
    with ProcessLock(path) as guard:
        assert attempt() == "held"
        with pytest.raises(AlreadyRunning):
            ProcessLock(path)
    guard.close()  # Repeated cleanup is safe.
    assert path.exists()  # Reusing one inode avoids unlink/recreate races.
    assert attempt() == "available"


def test_lock_is_released_when_process_exits_without_cleanup(tmp_path):
    path = tmp_path / "process.lock"
    child = '''
import os, sys
from pathlib import Path
from companion.process_lock import ProcessLock
guard = ProcessLock(Path(sys.argv[1]))
os._exit(0)
'''
    subprocess.run([sys.executable, "-c", child, str(path)], cwd=ROOT, timeout=15, check=True)
    with ProcessLock(path):
        pass


def test_windows_state_uses_local_appdata_and_detects_legacy_state(monkeypatch, tmp_path):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(storage.sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert storage.default_data_dir() == tmp_path / "local" / "draft-kit"
    monkeypatch.delenv("LOCALAPPDATA")
    assert storage.default_data_dir() == home / "AppData" / "Local" / "draft-kit"
    legacy = home / ".local" / "share" / "career-composer"
    legacy.mkdir(parents=True)
    (legacy / "state.enc").touch()
    assert storage.default_data_dir() == legacy


@pytest.mark.parametrize("platform,detail", [("win32", "Credential Locker"), ("darwin", "Keychain")])
def test_desktop_os_never_silently_falls_back_to_key_files(monkeypatch, tmp_path, platform, detail):
    monkeypatch.delenv("CAREER_COMPOSER_KEY_DIR", raising=False)
    monkeypatch.setattr(storage.sys, "platform", platform)
    def unavailable(*args):
        raise RuntimeError("credential store locked")
    monkeypatch.setattr(keyring, "get_password", unavailable)
    with pytest.raises(RuntimeError, match=detail):
        storage.encryption_key(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_windows_credential_key_is_reused_after_restart(monkeypatch, tmp_path):
    monkeypatch.delenv("CAREER_COMPOSER_KEY_DIR", raising=False)
    monkeypatch.setattr(storage.sys, "platform", "win32")
    credentials = {}
    monkeypatch.setattr(keyring, "get_password", lambda service, account: credentials.get((service, account)))
    monkeypatch.setattr(keyring, "set_password", lambda service, account, value: credentials.__setitem__((service, account), value))
    first, location = storage.encryption_key(tmp_path)
    second, _ = storage.encryption_key(tmp_path)
    assert first == second and location == "system keychain"
    assert list(credentials) == [("career-composer", str(tmp_path.resolve()))]


def test_failed_dependency_install_is_retried_and_successful_setup_is_reused(monkeypatch, tmp_path):
    (tmp_path / "requirements.txt").write_text("example==1\n")
    environment = tmp_path / ".venv"
    environment.mkdir()
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python.parent.mkdir(exist_ok=True)
    python.touch()
    calls = []
    fail = True
    def install(command, **kwargs):
        calls.append(command)
        if "-r" in command and fail:
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr(start.subprocess, "run", install)
    with pytest.raises(subprocess.CalledProcessError):
        start.prepare_environment(tmp_path)
    assert not (environment / "composer-requirements-hash").exists()
    fail = False
    assert start.prepare_environment(tmp_path) == python
    count = len(calls)
    start.prepare_environment(tmp_path)
    assert len(calls) == count
    (tmp_path / "requirements.txt").write_text("example==2\n")
    start.prepare_environment(tmp_path)
    assert len(calls) > count
