import asyncio
import threading
from pathlib import Path

import uvicorn

from companion.app import Settings, create_app
from companion.process_lock import AlreadyRunning, ProcessLock


class CompanionController:
    """Start/stop one local service without exposing OAuth credentials to the GUI."""
    def __init__(self, settings: Settings, *, key=None):
        self.settings = settings
        self.key = key
        self.app = None
        self.server = None
        self.thread = None
        self.guard = None
        self.error = ""

    @property
    def running(self):
        return bool(self.server and self.server.started and self.thread and self.thread.is_alive() and not self.server.should_exit)

    @property
    def busy(self):
        return bool(self.thread and self.thread.is_alive())

    @property
    def pairing_code(self):
        return self.app.state.pair_code if self.running else ""

    def start(self):
        if self.busy:
            return
        self.error = ""
        self.settings.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            guard = ProcessLock(self.settings.data_dir / "process.lock")
        except AlreadyRunning:
            raise RuntimeError("Another companion is running. Close it before starting this app.") from None
        try:
            self.app = create_app(self.settings, key=self.key)
            self.server = uvicorn.Server(uvicorn.Config(
                self.app, host="127.0.0.1", port=self.settings.port, access_log=False,
                log_level="critical", workers=1, timeout_graceful_shutdown=5,
            ))
        except Exception:
            guard.close()
            raise
        self.guard = guard
        self.thread = threading.Thread(target=self._serve, daemon=True, name="draft-kit-local")
        self.thread.start()

    def _serve(self):
        try:
            asyncio.run(self.server.serve())
        except BaseException:
            self.error = f"Could not start the companion. Check whether port {self.settings.port} is already in use."
        finally:
            if self.guard:
                self.guard.close()
                self.guard = None

    def stop(self):
        if self.server:
            self.server.should_exit = True

    def wait(self, timeout=10):
        if self.thread:
            self.thread.join(timeout)
        return not self.busy
