# Build desktop installers

Normal source users follow README.md. **Installers must be built on their target OS**: Windows for the `.exe`, macOS for the `.pkg`. PyInstaller is not a cross compiler. The repository deliberately contains source/build configuration, not large generated binaries.

## Windows installer using GitHub Actions

1. Upload this repository, including `.github/workflows/build-windows.yml` and the prebuilt `extension/dist`.
2. Open **Actions → Build Windows installer → Run workflow**.
3. The Windows x64 runner installs Inno Setup, bundles the app, and runs its noninteractive self-test. It then builds and silently installs the per-user installer into a temporary folder, checks the installed runtime/PDF worker and uninstalls it.
4. Download the successful **draft-kit-Windows-x64-unsigned-beta** artifact. It contains the setup `.exe`, extension ZIP, SHA-256 checksums and INSTALL.md.
5. Test the downloaded app on a fresh Windows user account, including tray menu, clipboard, Credential Locker, real ChatGPT sign-in/draft, résumé upload and optional startup. CI uses injected test keys and does not validate those real-account interactions.

No Windows signing secret is required for this unsigned beta job. The job uploads temporary build artifacts; it does not create a GitHub Release or publish to an audience. Runtime self-tests must succeed before packaging, and installed-runtime checks must succeed before artifact upload.

### Build locally on Windows

Install 64-bit x64 Python 3.12 and [Inno Setup](https://jrsoftware.org/isinfo.php). From the repository root in PowerShell:

```powershell
py -3.12 scripts/build_windows.py
```

`ISCC.exe` is found on PATH or under the normal Inno Setup installation directories. Set `$env:DRAFT_KIT_ISCC` to its full path if necessary. The first build creates `build/windows/venv`, installs packaging dependencies and creates the `.ico` from the existing draft-kit icon.

Output: `release/draft-kit-0.9.0-windows-x64-setup-unsigned-beta.exe`, a matching extension ZIP, checksums and INSTALL.md. End users run Setup; they do not need Python or this command.

The windowless tray executable and a console résumé-worker executable share one bundled runtime. The worker uses pipes and `CREATE_NO_WINDOW`, so résumé import can run without flashing a console. The GUI supplies null standard streams for logging compatibility; the worker preserves its real pipes and UTF-8 protocol. Frozen self-tests write a report file because a windowless executable has no visible stdout.

The installer is per-user, creates normal shortcuts and an uninstaller, and retains saved context/credentials on uninstall. Login startup is disabled by default and optional in the tray menu. A named mutex prevents upgrading/uninstalling a running tray app. No Windows service, scheduled task or administrator permission is installed.

### Windows signing

This build currently emits **unsigned beta** packages. For wider distribution, use an appropriate Windows code-signing identity/service to sign both bundled executables and the final installer, timestamp signatures and verify them before publishing. Signing policy/provider configuration is not automated here. Do not promise that a signature alone removes every Windows reputation warning. Never put certificates/private keys in the repository. See [Microsoft SignTool](https://learn.microsoft.com/en-us/windows/win32/seccrypto/signtool).

## macOS installer using GitHub Actions

Open **Actions → Build macOS installers → Run workflow** and choose `unsigned-beta` or `notarized`. The existing workflow targets Apple Silicon and a best-effort Intel runner, performs native dependency/runtime checks and uploads artifacts. Download tested packages rather than asking users to run the build script.

For notarization, configure these GitHub Actions secrets:

| Secret | Contents |
| --- | --- |
| `MACOS_SIGNING_P12_BASE64` | Base64 .p12 containing both Developer ID identities and private keys |
| `MACOS_SIGNING_P12_PASSWORD` | Password protecting that .p12 |
| `DRAFT_KIT_APP_SIGNING_IDENTITY` | Developer ID Application certificate identity |
| `DRAFT_KIT_INSTALLER_SIGNING_IDENTITY` | Developer ID Installer certificate identity |
| `APPLE_ID` | Apple account used for notarization |
| `APPLE_APP_PASSWORD` | App-specific password |
| `APPLE_TEAM_ID` | Developer team ID |

The helper imports identities into a temporary keychain, saves a notary profile, then restores the previous keychain search list and removes temporary credentials in cleanup. The notarized build signs, submits, staples/validates and assesses the installer. It stops on failure; no public release is automatic.

### Build locally on macOS

Use Python 3.11+, current Xcode Command Line Tools and the matching CPU architecture:

```bash
python3 scripts/build_macos.py
```

It creates a self-contained native menu-bar app and package under `release/`. Python and PyObjC are bundled for end users. Tkinter is excluded.

The pinned cryptography 50.0.2 dropped upstream Intel macOS support/wheels. Intel builds remain best effort and need Rust, OpenSSL headers and static archives (`brew install openssl@3 rust`, or `DRAFT_KIT_OPENSSL_DIR` pointing to the prefix). The builder forces static OpenSSL linkage, bypasses stale wheels and checks native dependencies before/after freezing. This preserves the prior repair for the bundled `_SSL_get0_group_name` collision. Apple Silicon requires the official wheel. Keep Python/Homebrew architectures consistent.

For a signed/notarized local build, install your Developer ID Application and Installer identities in Keychain and prepare a notarytool profile:

```bash
export DRAFT_KIT_APP_SIGNING_IDENTITY='Developer ID Application: YOUR NAME (TEAM ID)'
export DRAFT_KIT_INSTALLER_SIGNING_IDENTITY='Developer ID Installer: YOUR NAME (TEAM ID)'
export DRAFT_KIT_NOTARY_PROFILE='draft-kit-notary'
python3 scripts/build_macos.py --signed --notarize
```

Test the actual downloaded package on a fresh Mac: Finder launch, Keychain, pairing, résumé import, a real AI draft, menu controls, login enable/disable, restart and disconnect. Native builds/signing are not validated by Linux source tests.

## Repository and release artifacts

Keep `extension/dist` committed so source users do not need Node.js. Keep tests, workflow files, specs, installer scripts, dependency manifests, icon sources/assets and license notices. They are required to maintain or reproduce the builds.

Do not commit `build/`, `release/`, `.venv/`, node_modules, caches, test state, compiled installers, logs, résumés, profile exports or credentials. Put personal working files outside this repository. Generated `.ico`/`.icns` and collected bundle licenses belong under ignored build paths; release downloads belong in GitHub Releases.

The cleaned source ZIP is produced with `python3 scripts/package_source.py` (or `py -3 scripts/package_source.py`). It uses an allowlist so local environments and personal files are not pulled into the upload by accident.

## Primary references

- [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html)
- [Windowed Python standard streams](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
- [pystray tray/menu API](https://pystray.readthedocs.io/en/latest/usage.html)
- [Inno Setup per-user privileges](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)
- [Apple Developer ID](https://developer.apple.com/developer-id/)
