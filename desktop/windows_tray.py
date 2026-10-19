"""Windows tray UI. Native dependencies are imported only when used on Windows."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import threading

from companion.app import Settings
from companion.process_lock import AlreadyRunning
from companion.storage import default_data_dir
from .controller import CompanionController
from .extension_files import revealable_extension
from .session import BackgroundSession

MUTEX_NAME = r"Local\draft-kit-desktop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


class DesktopMutex:
    """Expose the same named mutex that the installer checks during upgrades."""
    def __init__(self):
        from ctypes import wintypes
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        self.api.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.api.CreateMutexW.restype = wintypes.HANDLE
        self.api.CloseHandle.argtypes = [wintypes.HANDLE]
        self.api.CloseHandle.restype = wintypes.BOOL
        self.handle = self.api.CreateMutexW(None, False, MUTEX_NAME)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
            self.close()
            raise AlreadyRunning("draft-kit is already running. Check the system tray's hidden icons.")

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None


def message(title, text):
    from ctypes import wintypes
    api = ctypes.WinDLL("user32", use_last_error=True)
    api.MessageBoxW.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    api.MessageBoxW.restype = ctypes.c_int
    api.MessageBoxW(None, text, title, 0x40)


def startup_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            command, _ = winreg.QueryValueEx(key, "draft-kit")
        return command == subprocess.list2cmdline([sys.executable])
    except OSError:
        return False


def set_startup(enabled):
    import winreg
    if not getattr(sys, "frozen", False):
        raise RuntimeError("Open at login is available in the installed app.")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, "draft-kit", 0, winreg.REG_SZ, subprocess.list2cmdline([sys.executable]))
        else:
            try:
                winreg.DeleteValue(key, "draft-kit")
            except FileNotFoundError:
                pass


class TrayApp:
    def __init__(self, session=None):
        self.session = session or BackgroundSession(CompanionController(Settings(default_data_dir())))
        self.lock = threading.RLock()
        self.icon = None
        self.last_state = None

    @property
    def available(self):
        return self.session.controller.running and not self.session.restart_pending and not self.session.quitting

    def act(self, operation):
        with self.lock:
            operation()
            self.refresh()

    def copy_code(self, icon=None, item=None):
        with self.lock:
            if self.available:
                try:
                    import pyperclip
                    pyperclip.copy(self.session.controller.pairing_code)
                    self.icon.notify("Pairing code copied. Paste it in the extension's Connect tab.", "draft-kit")
                except Exception:
                    message("Could not copy", "The clipboard is busy. Try Copy pairing code again.")

    def toggle(self, icon=None, item=None):
        self.act(self.session.stop if self.session.controller.busy else self.session.start)

    def restart(self, icon=None, item=None):
        self.act(self.session.restart)

    def toggle_demo(self, icon=None, item=None):
        self.act(lambda: self.session.set_demo(not self.session.controller.settings.demo))

    def quit(self, icon=None, item=None):
        self.act(self.session.quit)

    def toggle_startup(self, icon=None, item=None):
        try:
            set_startup(not startup_enabled())
        except Exception:
            message("Open at login unavailable", "Check Windows Settings > Apps > Startup, or open draft-kit from the Start menu.")

    def reveal_extension(self, icon=None, item=None):
        try:
            folder = revealable_extension(self.session.controller.settings.data_dir)
            os.startfile(str(folder))
        except Exception:
            message("Extension unavailable", "Download the extension from the same release and extract it to a permanent folder.")

    def setup(self, icon=None, item=None):
        message("Connect draft-kit", "1. Choose Show extension for beta install.\n2. In Chrome, open chrome://extensions. Enable Developer mode and Load unpacked that folder.\n3. In draft-kit, use http://127.0.0.1:1455.\n4. Copy the pairing code from this tray menu and pair.\n5. Continue with ChatGPT, add your context and draft.\n\nKeep draft-kit running. Right-click its tray icon for controls.")

    def refresh(self):
        if not self.icon:
            return
        state = (self.session.status, self.session.detail)
        if state != self.last_state:
            self.icon.title = ("draft-kit - " + self.session.status)[:127]
            self.icon.update_menu()
            if self.session.error or self.session.controller.error:
                self.icon.notify(self.session.detail, "draft-kit could not start")
            self.last_state = state

    def tick(self):
        with self.lock:
            done = self.session.poll()
            self.refresh()
            if done:
                self.icon.stop()
            return done

    def create_icon(self):
        import pystray
        from PIL import Image
        item = pystray.MenuItem
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).parents[1]))
        with Image.open(root / "extension/dist/icons/128.png") as source:
            image = source.copy()
        return pystray.Icon("draft-kit", image, "draft-kit", pystray.Menu(
            item(lambda _: "draft-kit - " + self.session.status, None, enabled=False),
            item(lambda _: self.session.detail, None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("Copy pairing code", self.copy_code, enabled=lambda _: self.available),
            item("New pairing code", self.restart, enabled=lambda _: self.available),
            item(lambda _: "Stop companion" if self.session.controller.busy else "Start companion", self.toggle),
            pystray.Menu.SEPARATOR,
            item("Setup instructions", self.setup, default=True),
            item("Show extension for beta install", self.reveal_extension),
            item("Open at login", self.toggle_startup, checked=lambda _: startup_enabled(), enabled=lambda _: bool(getattr(sys, "frozen", False))),
            item("Demo mode", self.toggle_demo, checked=lambda _: self.session.controller.settings.demo),
            pystray.Menu.SEPARATOR,
            item("Quit draft-kit", self.quit),
        ))

    def run(self):
        self.icon = self.create_icon()
        def setup(icon):
            icon.visible = True
            self.act(self.session.start)
            def monitor():
                while not self.tick():
                    threading.Event().wait(.3)
            threading.Thread(target=monitor, name="draft-kit-tray-monitor", daemon=True).start()
        try:
            self.icon.run(setup=setup)
        finally:
            self.session.quit()
            self.session.controller.wait()


def main():
    try:
        guard = DesktopMutex()
    except AlreadyRunning as error:
        message("draft-kit", str(error))
        return
    try:
        TrayApp().run()
    finally:
        guard.close()
