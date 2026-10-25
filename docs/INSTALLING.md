# Install the desktop companion

This guide is for **compiled release installers**. The repository source ZIP does not contain precompiled installers. Maintainers produce them using [BUILDING.md](BUILDING.md). To run directly from source on Windows/macOS, use [README.md](../README.md).

## Windows — x64 installer

Target: Windows 10 1809+ or Windows 11, x64. Native ARM64 and 32-bit builds are not supplied.

1. Download `draft-kit-VERSION-windows-x64-setup-unsigned-beta.exe` from the maintainer's validated release. The current build pipeline produces an unsigned beta; Windows may warn about its publisher. Use a build whose origin you trust. A public installer should be signed; do not disable Windows security tools to install it.
2. Run Setup as your normal Windows user. It installs to `%LOCALAPPDATA%\Programs\draft-kit`, adds a Start-menu shortcut and offers an optional desktop shortcut. No administrator session, Python or Node.js is needed.
3. Open draft-kit from Start. Find its blue document icon in the system tray near the clock, possibly inside the **^ hidden icons** area. Right-click it for controls. There is no persistent window or terminal.
4. Choose **Show extension for beta install**. In Chrome, open `chrome://extensions`, enable Developer mode, click Load unpacked and select the folder that opened. Keep that folder in place.
5. Click the Chrome extension icon. Under Connect, use `http://127.0.0.1:1455`. In the tray menu choose **Copy pairing code**, paste it into the extension and pair.
6. Continue with an eligible ChatGPT account, grant plan usage, upload/paste your professional context, review and save. README.md explains drafting and revisions.

**Start/stop:** use Start companion / Stop companion in the tray menu. New pairing code restarts the local service and issues a fresh ten-minute code. Demo mode restarts it in template mode without AI requests. Quit draft-kit stops the companion and removes the tray icon.

**Open at login** is opt-in and initially off. The installed app records its quoted executable path under your user account's Windows Run registry key. Windows Settings → Apps → Startup can also disable it. Uninstall removes draft-kit's startup entry. Source mode does not enable this setting.

**Update:** quit the tray app, run the newer installer and reopen it. Setup checks for an already running tray app and asks you to close it. Reload the unpacked extension in Chrome after the app update. The app has no automatic updater.

**Uninstall:** quit the app and use Windows Settings → Apps → Installed apps → draft-kit → Uninstall. Remove the Chrome extension separately. Saved encrypted data under `%LOCALAPPDATA%\draft-kit` and its credential-store key remain until you deliberately remove them; disconnect/clear profile before uninstalling if desired. The revealed extension folder is also under that data directory.

## macOS — package installer

Use arm64 for Apple Silicon or x86_64 for a best-effort Intel build. The optional app targets macOS 13+. Intel support has an upstream encryption-dependency limitation explained in BUILDING.md.

1. Install the matching `.pkg` and open draft-kit from Applications.
2. Find **DK** in the menu bar. There is no persistent app window or Dock icon.
3. If Keychain asks for access to `career-composer`, enter your login Keychain password (normally your Mac login password). Allow grants access this time; Always Allow grants ongoing access to this item. The older service name preserves saved beta data.
4. Use **Show extension for beta install**, load that folder in Chrome Developer mode, and choose **DK → Copy pairing code** to pair at `http://127.0.0.1:1455`.
5. Continue with ChatGPT and follow README.md to add context and draft.

Keep DK running while drafting. Open at login is optional and off by default; macOS may request approval in System Settings → General → Login Items. Disable it before removing the app. Quit draft-kit before installing an update. Retain the saved data directory if you want to keep your context; README.md lists its path.

### “Apple could not verify … is free of malware”

An `unsigned-beta.pkg` has no Developer ID installer signature or Apple notarization ticket. That warning is separate from a Python/OpenSSL runtime failure. The warning alone does not establish whether a file is safe.

For your own build or a beta whose origin/integrity you trust: try opening it, dismiss the warning, then open **System Settings → Privacy & Security → Open Anyway → Open**. The installed app may require its own per-item exception. A managed Mac may prohibit it. A “will damage your computer” warning needs investigation rather than an override. Do not disable Gatekeeper globally.

For audience distribution, the maintainer should sign the app and installer with Developer ID certificates, notarize, staple/validate and test the downloaded package. See [Apple's installation guidance](https://support.apple.com/en-us/102445) and [Developer ID documentation](https://developer.apple.com/developer-id/).

## Shared requirements and troubleshooting

Each user connects their own eligible ChatGPT account; AI requests use that account's allowance. The demo works without sign-in. Pairing codes expire after ten minutes and are single-use, while saved pairing survives restarting. Use New pairing code if needed. Ten failed attempts lock pairing until the companion restarts, so paste the code instead of retyping it; New pairing code clears the lock. The extension also needs Chrome 116 or newer.

Only one companion can use the same saved-state directory. Quit the old desktop/source companion before switching. Startup fails if Windows Credential Locker or Mac Keychain is unavailable. Check the tray/menu status and OS credential store; no hosted backend is required.

The app listens only on `127.0.0.1`. It does not need a public server, inbound LAN firewall rule or port forwarding. Public job links and AI generation still require internet access. Chrome's Developer mode remains necessary for an unpacked extension; managed browsers may block it.
