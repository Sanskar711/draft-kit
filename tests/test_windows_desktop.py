import asyncio
import base64
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from companion import resumes
from desktop import windows_tray
from scripts import build_windows as builder
from scripts.package_source import package


@pytest.mark.parametrize("frozen,name,expected", [(True, "draft-kit.exe", "draft-kit-worker.exe"), (False, "pythonw.exe", "python.exe")])
def test_windows_resume_import_uses_a_pipe_capable_hidden_worker(monkeypatch, frozen, name, expected):
    monkeypatch.setattr(resumes.sys, "platform", "win32")
    monkeypatch.setattr(resumes.sys, "frozen", frozen, raising=False)
    monkeypatch.setattr(resumes.sys, "executable", str(Path("Application Folder") / name))
    monkeypatch.setattr(resumes.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    commands = []
    class Worker:
        returncode = 0
        async def communicate(self, data):
            assert data.startswith(b"A professional")
            return json.dumps({"text": "Reviewed experience", "warnings": []}).encode(), b""
    async def spawn(*args, **kwargs):
        commands.append((args, kwargs))
        return Worker()
    monkeypatch.setattr(resumes.asyncio, "create_subprocess_exec", spawn)
    body = base64.b64encode(b"A professional with extensive experience managing cross-functional projects.").decode()
    result = asyncio.run(resumes.read_resume("resume.txt", body))
    command, options = commands[0]
    assert Path(command[0]).name == expected
    assert options["creationflags"] == 0x08000000
    assert result["text"] == "Reviewed experience"


def test_unicode_resume_survives_worker_output():
    text = "प्रोजेक्ट संचालन और टीम समन्वय का अनुभव।\n日本語の職務経歴とプロジェクト管理経験。"
    result = asyncio.run(resumes.read_resume("resume.txt", base64.b64encode(text.encode()).decode()))
    assert result["text"] == text


def test_windows_build_rejects_non_windows_before_native_commands(monkeypatch):
    monkeypatch.setattr(builder.sys, "platform", "linux")
    with pytest.raises(RuntimeError, match="Build on Windows"):
        builder.validate_host()


def test_runtime_check_rejects_stale_success_report(monkeypatch, tmp_path):
    report = tmp_path / "report.json"
    report.write_text('{"ok": true}')
    monkeypatch.setattr(builder, "run", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError, match="did not report success"):
        builder.verify_runtime(tmp_path / "app.exe", report)
    assert not report.exists()


def test_runtime_check_accepts_new_success_report(monkeypatch, tmp_path):
    report = tmp_path / "report.json"
    def run(command, **kwargs):
        assert "--self-test" in command and kwargs["timeout"] == 90
        report.write_text('{"ok": true}')
    monkeypatch.setattr(builder, "run", run)
    builder.verify_runtime(tmp_path / "app.exe", report)


def test_windows_tray_quit_cancels_pending_restart_before_stopping_icon():
    from desktop.session import BackgroundSession
    stopped = []
    controller = SimpleNamespace(busy=False, running=False, error="", settings=SimpleNamespace(demo=False, port=1455), stop=lambda: stopped.append("service"))
    session = BackgroundSession(controller)
    session.restart_pending = True
    app = windows_tray.TrayApp(session)
    app.icon = SimpleNamespace(stop=lambda: stopped.append("icon"), update_menu=lambda: None)
    app.quit()
    assert not session.restart_pending and session.quitting
    assert app.tick()
    assert stopped == ["service", "icon"]
    assert not app.available


def test_source_archive_keeps_required_builds_and_excludes_local_and_personal_files(tmp_path):
    root = tmp_path / "source"
    files = {
        "README.md": "Manual", "LICENSE": "License", "companion/__main__.py": "",
        "extension/dist/manifest.json": "{}", "extension/dist/sidepanel.js": "bundle",
        ".github/workflows/build-windows.yml": "workflow", "desktop/windows/installer.iss": "setup",
        "requirements-windows-build.txt": "deps", "docs/BUILDING.md": "build",
        "node_modules/ignore.js": "ignore", ".venv/ignore.py": "ignore", "release/setup.exe": "ignore",
        "tests/__pycache__/compiled.pyc": "ignore", "personal/resume.pdf": "ignore", ".env": "secret",
        "profile.json": "personal", "extension/resume.pdf": "personal", "desktop/build-licenses.txt": "generated",
    }
    for name, contents in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    output = package(root, tmp_path / "source.zip")
    import zipfile
    with zipfile.ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "draft-kit/extension/dist/manifest.json" in names
        assert "draft-kit/.github/workflows/build-windows.yml" in names
        assert "draft-kit/desktop/windows/installer.iss" in names
        assert len(names) == 9
