import asyncio
import base64
import io
import json
import zipfile

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject

from companion.app import Settings, create_app
from companion.errors import AppError
from companion.generation import selected_facts
from companion.models import GenerateRequest
from companion.resume_worker import extract
from companion.resumes import read_resume

TEXT = "Alex Rao\nExperience\nBuilt FastAPI services and reduced latency by 25%.\nEducation\nBachelor of Technology."


def pdf(text=True, encrypted=False):
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    if text:
        font = writer._add_object(DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")}))
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 50 750 Td (Alex Rao) Tj 0 -20 Td (Built FastAPI APIs and reduced latency by 25%.) Tj ET")
        page[NameObject("/Contents")] = writer._add_object(stream)
    if encrypted:
        writer.encrypt("password")
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def docx(xml=None):
    xml = xml or '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Alex Rao</w:t></w:r></w:p><w:p><w:r><w:t>Built FastAPI </w:t></w:r><w:r><w:t>APIs and reduced latency by 25%.</w:t></w:r></w:p></w:body></w:document>'
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", xml)
    return output.getvalue()


@pytest.mark.parametrize("extension,data", [(".pdf", pdf()), (".docx", docx()), (".txt", TEXT.encode())])
def test_formats_preserve_text_and_metrics(extension, data):
    result = extract(data, extension)
    assert "FastAPI" in result["text"] and "25%" in result["text"]
    assert result["warnings"]


@pytest.mark.parametrize("data,extension,match", [
    (pdf(text=False), ".pdf", "No readable text"),
    (pdf(encrypted=True), ".pdf", "unencrypted PDF"),
    (b"not pdf", ".pdf", "readable PDF"),
    (b"", ".txt", "under 5 MB"),
    (b"x" * (5 * 1024 * 1024 + 1), ".txt", "under 5 MB"),
    (b"\xff\xff", ".txt", "UTF-8"),
    (TEXT.encode(), ".doc", "PDF, DOCX or TXT"),
    (docx('<!DOCTYPE x [<!ENTITY secret SYSTEM "file:///tmp/secret">]><x/>'), ".docx", "could not be read"),
])
def test_unreadable_formats_are_actionable(data, extension, match):
    with pytest.raises(ValueError, match=match):
        extract(data, extension)


def test_docx_expansion_and_text_bounds():
    with pytest.raises(ValueError, match="too large"):
        extract(docx("x" * (8 * 1024 * 1024 + 1)), ".docx")
    result = extract((TEXT * 1000).encode(), ".txt")
    assert len(result["text"]) == 48000 and any("shortened" in note for note in result["warnings"])


def test_isolated_worker_and_invalid_base64():
    result = asyncio.run(read_resume("../resume.TXT", base64.b64encode(TEXT.encode()).decode()))
    assert result["filename"] == "resume.TXT" and "25%" in result["text"]
    with pytest.raises(AppError, match="could not be read"):
        asyncio.run(read_resume("resume.txt", "not valid base64"))
    result = asyncio.run(read_resume("resume.pdf", base64.b64encode(pdf()).decode()))
    assert "25%" in result["text"]
    with pytest.raises(AppError, match="could not be read"):
        asyncio.run(read_resume("resume.docx", base64.b64encode(b"not a zip").decode()))


def test_upload_requires_pairing_and_saves_only_reviewed_context(tmp_path):
    app = create_app(Settings(tmp_path / "data", demo=True), key=Fernet.generate_key())
    origin = "chrome-extension://" + "a" * 32
    body = {"filename": "resume.txt", "content_base64": base64.b64encode(TEXT.encode()).decode()}
    with TestClient(app, base_url="http://127.0.0.1:1455") as client:
        assert client.post("/resume/import", headers={"Origin": origin}, json=body).status_code == 401
        paired = client.post("/pair", headers={"Origin": origin}, json={"code": app.state.pair_code, "extension_id": "a" * 32})
        headers = {"Origin": origin, "X-Composer-Token": paired.json()["pair_token"]}
        result = client.post("/resume/import", headers=headers, json=body)
        assert result.status_code == 200 and "25%" in result.json()["text"]
        assert app.state.vault.profile().facts == []
        assert list((tmp_path / "data").iterdir()) == [app.state.vault.path]
        profile = {"name": "Alex", "resume_filename": "resume.txt", "facts": [{"id": "resume-role", "text": "Built FastAPI APIs and reduced latency by 25%.", "confirmed": False, "source": "resume", "source_filename": "resume.txt"}]}
        assert client.put("/profile", headers=headers, json=profile).status_code == 200
        request = GenerateRequest(mode="dm", model="offline-demo", prompt="Write a referral DM", tone="Professional", job_input="FastAPI job")
        assert selected_facts(app.state.vault.profile(), request) == []
        profile["facts"][0]["confirmed"] = True
        client.put("/profile", headers=headers, json=profile)
        assert selected_facts(app.state.vault.profile(), request)[0]["source"] == "resume"
        assert b"resume-role" not in app.state.vault.path.read_bytes()
        assert not app.state.resume_lock.locked()


def test_manifest_has_no_linkedin_or_scripting_permissions():
    from pathlib import Path
    manifest = json.loads((Path(__file__).parents[1] / "extension/manifest.json").read_text())
    assert "scripting" not in manifest["permissions"]
    assert not manifest.get("optional_host_permissions")
    assert manifest["host_permissions"] == ["http://127.0.0.1/*"]
