"""Bounded text extraction worker. No file is written or document code executed."""
import io
import json
import re
import sys
import zipfile
from xml.etree import ElementTree

MAX_FILE = 5 * 1024 * 1024
MAX_TEXT = 48000


def extract(data: bytes, extension: str) -> dict:
    if not data or len(data) > MAX_FILE:
        raise ValueError("Choose a résumé under 5 MB.")
    if extension == ".pdf":
        if b"%PDF-" not in data[:1024]:
            raise ValueError("This file is not a readable PDF.")
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Upload an unencrypted PDF.")
        if len(reader.pages) > 20:
            raise ValueError("Choose a résumé with 20 pages or fewer.")
        parts = []
        for page in reader.pages:
            content = page.get_contents()
            if content and len(content.get_data()) > 8 * 1024 * 1024:
                raise ValueError("This PDF is too complex. Upload DOCX or paste your profile.")
            parts.append(page.extract_text() or "")
            if sum(len(part) for part in parts) > MAX_TEXT:
                break
        text = "\n\n".join(parts)
    elif extension == ".docx":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 1000 or sum(info.file_size for info in infos) > 20 * 1024 * 1024:
                raise ValueError("This DOCX is too large to read. Paste your profile instead.")
            info = archive.getinfo("word/document.xml")
            if info.file_size > 8 * 1024 * 1024:
                raise ValueError("This DOCX is too large to read. Paste your profile instead.")
            xml = archive.read(info)
        if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
            raise ValueError("This DOCX could not be read. Paste your profile instead.")
        root = ElementTree.fromstring(xml)
        namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        parts = []
        for paragraph in root.iter(namespace + "p"):
            parts.append("".join(node.text or "" if node.tag == namespace + "t" else "\n" if node.tag == namespace + "br" else "\t" if node.tag == namespace + "tab" else "" for node in paragraph.iter()))
        text = "\n".join(parts)
    elif extension == ".txt":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeError:
            raise ValueError("Save the TXT file as UTF-8, or paste your profile.") from None
    else:
        raise ValueError("Choose a PDF, DOCX or TXT résumé.")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text).strip()
    if len(re.sub(r"\s", "", text)) < 30:
        raise ValueError("No readable text found. Use a text-based PDF, DOCX or paste your profile.")
    warnings = ["Review the extracted text. Columns, line breaks and section order may need editing."]
    if len(text) > MAX_TEXT:
        warnings.append("Long résumé shortened. Keep your most relevant experience.")
    return {"text": text[:MAX_TEXT], "warnings": warnings}


def main():
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (10, 12))
        resource.setrlimit(resource.RLIMIT_AS, (384 * 1024 * 1024, 384 * 1024 * 1024))
    except (ImportError, ValueError, OSError):
        pass
    try:
        result = extract(sys.stdin.buffer.read(MAX_FILE + 1), sys.argv[1])
    except ValueError as error:
        result = {"error": str(error) if str(error).startswith(("Choose", "Upload", "This", "No readable", "Save")) else "This résumé could not be read. Try another file or paste your profile."}
    except Exception:
        result = {"error": "This résumé could not be read. Try another file or paste your profile."}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=False).encode("utf-8") + b"\n")


if __name__ == "__main__":
    main()
