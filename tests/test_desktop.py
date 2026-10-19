import socket
import time

import httpx
import pytest
from cryptography.fernet import Fernet

from companion.app import Settings
from desktop.controller import CompanionController
from desktop.session import BackgroundSession
from desktop.extension_files import revealable_extension


def available_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def ready(controller):
    deadline = time.monotonic() + 5
    while not controller.running and time.monotonic() < deadline:
        time.sleep(.02)
    assert controller.running, controller.error


def test_desktop_start_pair_stop_and_restart(tmp_path):
    controller = CompanionController(Settings(tmp_path, port=available_port(), demo=True), key=Fernet.generate_key())
    try:
        controller.start()
        ready(controller)
        code = controller.pairing_code
        address = "http://127.0.0.1:" + str(controller.settings.port)
        with httpx.Client(trust_env=False) as client:
            assert client.get(address + "/health").status_code == 200
            result = client.post(address + "/pair", headers={"Origin": "chrome-extension://" + "a" * 32}, json={"code": code, "extension_id": "a" * 32})
            assert result.status_code == 200
        controller.stop()
        assert controller.wait()
        assert not controller.running and controller.pairing_code == ""
        controller.start()
        ready(controller)
        assert controller.pairing_code != code
    finally:
        controller.stop()
        assert controller.wait()


def test_two_desktop_instances_cannot_share_state(tmp_path):
    key = Fernet.generate_key()
    first = CompanionController(Settings(tmp_path, port=available_port(), demo=True), key=key)
    second = CompanionController(Settings(tmp_path, port=available_port(), demo=True), key=key)
    try:
        first.start()
        ready(first)
        with pytest.raises(RuntimeError, match="Another companion"):
            second.start()
        assert first.running
    finally:
        first.stop()
        assert first.wait()


def test_busy_port_returns_error_and_releases_state_guard(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        controller = CompanionController(Settings(tmp_path, port=listener.getsockname()[1], demo=True), key=Fernet.generate_key())
        controller.start()
        assert controller.wait()
        assert controller.error and not controller.running and controller.guard is None


def poll_ready(session):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        session.poll()
        if session.controller.running and not session.restart_pending:
            return
        time.sleep(.02)
    raise AssertionError(session.detail)


def test_menu_session_mode_restart_and_quit_cancel_pending_restart(tmp_path):
    controller = CompanionController(Settings(tmp_path, port=available_port(), demo=True), key=Fernet.generate_key())
    session = BackgroundSession(controller)
    try:
        session.start()
        poll_ready(session)
        old_code = controller.pairing_code
        session.set_demo(False)
        assert session.status == "Restarting…"
        poll_ready(session)
        with httpx.Client(trust_env=False) as client:
            health = client.get(f"http://127.0.0.1:{controller.settings.port}/health").json()
            assert health["mode"] == "chatgpt"
        assert session.status == "Running" and controller.pairing_code != old_code
        session.restart()
        session.quit()
        assert controller.wait()
        assert session.poll()
        assert not controller.running and not session.restart_pending
        session.start()
        assert not controller.busy
    finally:
        session.quit()
        assert controller.wait()


def test_menu_stop_cancels_restart_and_allows_manual_start(tmp_path):
    controller = CompanionController(Settings(tmp_path, port=available_port(), demo=True), key=Fernet.generate_key())
    session = BackgroundSession(controller)
    try:
        session.start()
        poll_ready(session)
        session.restart()
        session.stop()
        assert controller.wait()
        assert not session.poll() and session.status == "Stopped"
        session.start()
        poll_ready(session)
        assert session.status == "Running · Demo"
    finally:
        session.quit()
        assert controller.wait()


def test_beta_extension_keeps_stable_folder_when_upgraded(tmp_path):
    destination = revealable_extension(tmp_path)
    (destination / "manifest.json").write_text('{"version":"0.1.0"}')
    (destination / "sidepanel.js").write_text("old bundle")
    assert revealable_extension(tmp_path) == destination
    assert (destination / "sidepanel.js").read_text() != "old bundle"
    assert (destination / "LICENSE").is_file()
