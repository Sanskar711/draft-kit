# Build this spec on macOS with the matching CPU architecture.
import json
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

project = Path(SPECPATH).parent
version = json.loads((project / "extension/dist/manifest.json").read_text())["version"]
datas = [(str(project / "extension/dist"), "extension/dist")]
datas += [(str(project / "desktop/menu-icon.png"), "desktop")]
datas += [(str(project / "desktop/build-licenses.txt"), "licenses"), (str(project / "LICENSE"), "licenses")]
datas += collect_data_files("certifi")
for package in ["fastapi", "starlette", "uvicorn", "httpx", "httpcore", "keyring", "PyJWT", "cryptography", "pydantic", "pypdf", "pyobjc-core", "pyobjc-framework-Cocoa", "pyobjc-framework-ServiceManagement"]:
    datas += copy_metadata(package)
hidden = collect_submodules("keyring.backends") + [
    "uvicorn.logging", "uvicorn.loops.asyncio", "uvicorn.protocols.http.h11_impl", "uvicorn.lifespan.on",
]
for module in ["AppKit", "Foundation", "CoreFoundation", "ServiceManagement", "objc"]:
    hidden += collect_submodules(module)
a = Analysis([str(project / "desktop/entrypoint.py")], pathex=[str(project)], binaries=[], datas=datas,
             hiddenimports=hidden, hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=["tkinter", "_tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="draft-kit", debug=False,
          bootloader_ignore_signals=False, strip=False, upx=False, console=False,
          target_arch=None, codesign_identity=os.environ.get("DRAFT_KIT_APP_SIGNING_IDENTITY") or os.environ.get("COMPOSER_APP_SIGNING_IDENTITY") or None,
          entitlements_file=str(project / "desktop/entitlements.plist"))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="draft-kit")
app = BUNDLE(coll, name="draft-kit.app", icon=str(project / "desktop/build-icon.icns"),
             # Preserve the existing app identity for upgrades and local pairing.
             bundle_identifier="com.careercomposer.desktop", info_plist={
                 "CFBundleShortVersionString": version, "CFBundleVersion": version,
                 "CFBundleName": "draft-kit", "CFBundleDisplayName": "draft-kit",
                 "NSHighResolutionCapable": True, "LSMinimumSystemVersion": "13.0",
                 "LSUIElement": True,
             })
