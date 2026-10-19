import asyncio
import base64
import binascii
import json
import subprocess
import sys
from pathlib import Path

from .errors import AppError

MAX_FILE = 5 * 1024 * 1024


async def read_resume(filename: str, content_base64: str) -> dict:
    filename = filename.replace("\\", "/").split("/")[-1]
    extension = Path(filename).suffix.lower()
    if extension not in (".pdf", ".docx", ".txt"):
        raise AppError("resume_type", "Choose a PDF, DOCX or TXT résumé.")
    try:
        data = base64.b64decode(content_base64, validate=True)
    except (ValueError, binascii.Error):
        raise AppError("resume_invalid", "This upload could not be read. Choose the file again.") from None
    if not data or len(data) > MAX_FILE:
        raise AppError("resume_size", "Choose a résumé under 5 MB.")
    command, options = worker_command(extension)
    process = await asyncio.create_subprocess_exec(
        *command, **options,
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(data), timeout=15)
        if process.returncode != 0 or len(output) > 300000:
            raise AppError("resume_unreadable", "This résumé is too complex to read. Try DOCX or paste your profile.")
        result = json.loads(output)
        if result.get("error"):
            raise AppError("resume_unreadable", result["error"])
        return {"filename": filename, **result}
    except (TimeoutError, ValueError):
        raise AppError("resume_unreadable", "This résumé could not be read. Try another file or paste your profile.") from None
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


def worker_command(extension):
    executable = Path(sys.executable)
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if sys.platform == "win32" else {}
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            executable = executable.with_name("draft-kit-worker.exe")
        command = [str(executable), "--resume-worker", extension]
    else:
        if sys.platform == "win32" and executable.name.lower() == "pythonw.exe":
            executable = executable.with_name("python.exe")
        command = [str(executable), "-I", str(Path(__file__).with_name("resume_worker.py")), extension]
    return command, options
