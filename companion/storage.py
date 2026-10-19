import json
import os
import secrets
import sys
from uuid import uuid4
from pathlib import Path
from threading import RLock

from cryptography.fernet import Fernet

from .models import Profile


def default_data_dir() -> Path:
    # Keep the beta's storage and Keychain identity through the draft-kit rename.
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "CareerComposer"
    if sys.platform == "win32":
        legacy = Path.home() / ".local" / "share" / "career-composer"
        if (legacy / "state.enc").exists():
            return legacy
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "draft-kit"
    return Path.home() / ".local" / "share" / "career-composer"


def atomic_private_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def encryption_key(data_dir: Path) -> tuple[bytes, str]:
    # A dedicated key directory supports noninteractive development on Linux.
    # macOS/Windows require the OS credential store, rather than falling back.
    key_dir_setting = os.environ.get("CAREER_COMPOSER_KEY_DIR")
    if not key_dir_setting:
        try:
            import keyring

            account = str(data_dir.resolve())
            saved = keyring.get_password("career-composer", account)
            if saved:
                return saved.encode(), "system keychain"
            key = Fernet.generate_key()
            keyring.set_password("career-composer", account, key.decode())
            return key, "system keychain"
        except Exception:
            if sys.platform == "darwin":
                raise RuntimeError(
                    "The macOS Keychain is unavailable. Unlock it and restart."
                ) from None
            if sys.platform == "win32":
                raise RuntimeError(
                    "Windows Credential Locker is unavailable. Run as your normal signed-in "
                    "Windows user and check Credential Manager, then restart."
                ) from None
    key_dir = Path(key_dir_setting).expanduser() if key_dir_setting else (
        Path.home() / ".config" / "career-composer" / "keys"
    )
    if key_dir.resolve() == data_dir.resolve() or data_dir.resolve() in key_dir.resolve().parents:
        raise RuntimeError("The encryption key directory must be outside the data directory.")
    key_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Isolate different data directories, including tests and demo sessions.
    import hashlib

    key_path = key_dir / (hashlib.sha256(str(data_dir.resolve()).encode()).hexdigest()[:24] + ".key")
    if not key_path.exists():
        atomic_private_write(key_path, Fernet.generate_key())
    os.chmod(key_path, 0o600)
    return key_path.read_bytes(), "private local key file"


class Vault:
    """Encrypted, atomic state. One companion process per data directory."""

    def __init__(self, data_dir: Path, key: bytes | None = None):
        data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(data_dir, 0o700)
        self.path = data_dir / "state.enc"
        self.lock = RLock()
        if key is None:
            key, self.key_storage = encryption_key(data_dir)
        else:
            self.key_storage = "injected test key"
        self.cipher = Fernet(key)
        if self.path.exists():
            self.state = json.loads(self.cipher.decrypt(self.path.read_bytes()))
        else:
            self.state = {"host_id": "urn:uuid:" + str(uuid4())}
            self.save()

    def save(self):
        with self.lock:
            atomic_private_write(self.path, self.cipher.encrypt(json.dumps(self.state).encode()))

    def profile(self) -> Profile:
        with self.lock:
            return Profile.model_validate(self.state.get("profile", {}))

    def put_profile(self, profile: Profile):
        with self.lock:
            self.state["profile"] = profile.model_dump()
            self.save()

