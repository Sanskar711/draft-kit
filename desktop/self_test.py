"""Noninteractive bundled-runtime test; no real account or Keychain access."""
import asyncio
import base64
import io
import json
import socket
import sys
import tempfile
import time
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from companion.app import Settings
from companion.resumes import read_resume
from .controller import CompanionController


def main():
    if sys.platform == "darwin":
        # Check bridge imports and Objective-C callbacks without opening UI,
        # registering a login item or touching a real Keychain/profile.
        from desktop.menubar import MenuDelegate
        assert MenuDelegate.alloc().init() is not None
        assert MenuDelegate.applicationShouldTerminate_.signature == b"Q@:@", "Mac termination callback must return NSUInteger."
    if sys.platform == "win32":
        from desktop.windows_tray import TrayApp
        import keyring.backends.Windows
        import pyperclip
        # Construct the native tray object without displaying it or accessing
        # real credentials/clipboard/startup settings.
        assert TrayApp().create_icon() is not None
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 50 750 Td (Coordinated a project and improved turnaround time by 20%.) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = io.BytesIO()
    writer.write(output)
    result = asyncio.run(read_resume("resume.pdf", base64.b64encode(output.getvalue()).decode()))
    assert "20%" in result["text"], "Bundled PDF worker failed."
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    with tempfile.TemporaryDirectory() as directory:
        controller = CompanionController(Settings(Path(directory), port=port, demo=True), key=Fernet.generate_key())
        try:
            controller.start()
            deadline = time.monotonic() + 10
            while not controller.running and time.monotonic() < deadline:
                time.sleep(.05)
            assert controller.running, controller.error
            address = "http://127.0.0.1:" + str(port)
            with httpx.Client(trust_env=False) as client:
                assert client.get(address + "/health").json()["ok"]
                paired = client.post(address + "/pair", headers={"Origin": "chrome-extension://" + "a" * 32}, json={"extension_id": "a" * 32, "code": controller.pairing_code})
                assert paired.status_code == 200
        finally:
            controller.stop()
            assert controller.wait(), "Companion did not stop."
    if "--self-test-report" in sys.argv:
        report = Path(sys.argv[sys.argv.index("--self-test-report") + 1])
        report.write_text(json.dumps({"ok": True, "checks": ["desktop imports", "PDF worker", "local service", "pairing", "shutdown"]}), encoding="utf-8")
    if sys.stdout is not None:
        print("PASS desktop runtime, PDF worker, local service, pairing and graceful shutdown", flush=True)
