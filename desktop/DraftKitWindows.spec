# Build on 64-bit Windows. Two executables share one bundled Python runtime.
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, copy_metadata

project = Path(SPECPATH).parent
build = project / "build/windows"
datas = [(str(project / "extension/dist"), "extension/dist"),
         (str(build / "licenses.txt"), "licenses"), (str(project / "LICENSE"), "licenses")]
datas += collect_data_files("certifi")
for package in ["fastapi", "starlette", "uvicorn", "httpx", "httpcore", "keyring", "PyJWT", "cryptography", "pydantic", "pypdf", "pystray", "pillow", "pyperclip"]:
    datas += copy_metadata(package)
a = Analysis([str(project / "desktop/entrypoint.py")], pathex=[str(project)], binaries=[], datas=datas,
             hiddenimports=["keyring.backends.Windows", "pystray._win32", "uvicorn.logging",
                            "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on"],
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=["tkinter", "_tkinter", "AppKit", "Foundation", "ServiceManagement",
                       "pystray._darwin", "pystray._xorg", "pystray._appindicator", "pystray._gtk"])
pyz = PYZ(a.pure)
app = EXE(pyz, a.scripts, [], exclude_binaries=True, name="draft-kit", console=False,
          icon=str(build / "draft-kit.ico"), debug=False, strip=False, upx=False)
# Windowed Python has no stdin/stdout on Windows. A console helper preserves the
# bounded resume parser's pipe protocol; CREATE_NO_WINDOW hides its console.
worker = EXE(pyz, a.scripts, [], exclude_binaries=True, name="draft-kit-worker", console=True,
             icon=str(build / "draft-kit.ico"), debug=False, strip=False, upx=False)
coll = COLLECT(app, worker, a.binaries, a.datas, strip=False, upx=False, name="draft-kit")
