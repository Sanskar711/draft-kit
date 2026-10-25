# draft-kit

Write job DMs and LinkedIn posts in a Chrome side panel, using your résumé or professional information as context. Run the companion on **your own computer** and load the included extension through Chrome Developer mode.

**Open-source beta · v0.9.0 · MIT license.** No hosted backend, paid server, API key, native installer or Chrome Web Store account is needed for this source setup. Python is required. Keep the local companion running while you use the extension.

> AI generation requires an **eligible ChatGPT Plus or Pro account** and permission to use its plan. Free-account AI generation is not promised. The demo works without a ChatGPT account. Live sign-in and real AI responses still need end-to-end verification; automated tests use a simulated provider.


## Choose your setup

| Setup | What users need | Companion controls |
| --- | --- | --- |
| Source on Windows/macOS | Python + Chrome; steps below | Terminal |
| Windows x64 installer | Compiled setup `.exe` + Chrome | System tray |
| Mac installer | Compiled `.pkg` + Chrome | DK menu bar |

The repository includes **Windows and Mac installer build workflows**, not precompiled installers. Maintainers run the matching GitHub Actions workflow and distribute its validated output. The Windows app bundles Python, installs per user and provides an uninstaller. End users do not run the build script. See [desktop installation](docs/INSTALLING.md) and [maintainer builds](docs/BUILDING.md). Native Windows installer execution is still awaiting a Windows build/test run.

## What it does

- Import a PDF, DOCX or TXT résumé, or paste your professional information. Review and approve facts before saving.
- Write a DM asking an employee for a referral or contacting the hiring team. Paste a JD or a public job link. Without a recipient name, use a generic greeting.
- Read accessible public job pages for role details. Paste the JD when a page requires login or cannot be read.
- Draft posts with a chosen tone and optional suggested hashtags.
- Edit drafts directly, describe changes in a modification box, apply revisions and restore the previous draft.
- Copy the result and paste it into LinkedIn yourself.

The profession-neutral placeholders, résumé/pasted context, drafting features, draft-kit branding, blue theme and icons are retained. The extension does not read LinkedIn profiles, conversations or recipient information, and does not send messages or publish posts for you.

## 1. Install prerequisites

| Requirement | Windows | macOS |
| --- | --- | --- |
| Browser | Current desktop Google Chrome; **116 minimum** | Current desktop Google Chrome; **116 minimum** |
| Python | **64-bit Python 3.12 recommended**, 3.11 minimum | Python 3.12 recommended, 3.11 minimum; use native Apple Silicon Python on M-series Macs |
| Credentials | Signed-in Windows user with Credential Manager available | Unlocked login Keychain |
| Internet | First dependency installation; ChatGPT sign-in/generation; public job links | Same |

Download Python from [python.org](https://www.python.org/downloads/). On Windows, enable the Python launcher / PATH options if offered. Close and reopen your terminal after installation. **Node.js and Git are optional for users**: the extension is already built in `extension/dist`.

Apple Silicon macOS and 64-bit x86 Windows are the primary setup targets. **Intel Mac users must first follow [the extra setup below](#intel-mac-extra-setup)**. Windows on ARM with native ARM Python is not validated; use a compatible x64 Python installation if your Windows system supports it. Python 3.15 and free-threaded Python builds are not tested.

## 2. Download the project

On this GitHub repository, choose **Code → Download ZIP**, extract it completely, and keep the project in a permanent folder such as `Documents/draft-kit`. A downloaded GitHub ZIP may have a name such as `draft-kit-main`; that is fine.

Open a terminal in the folder containing **this README**, `requirements.txt`, `companion/` and `extension/`. Do not run from inside the ZIP or from `extension/dist`.

If you use Git instead, clone this repository and open the cloned folder. The source and the prebuilt extension are both included.

## 3. Start your local companion

### Windows — PowerShell

Open PowerShell in the extracted project folder. For example, if you named it `draft-kit` under Documents:

```powershell
cd "$HOME\Documents\draft-kit"
py -3 scripts/start.py
```

If `py` is unavailable but `python --version` shows Python 3.11 or newer:

```powershell
python scripts/start.py
```

You can also double-click **Start draft-kit.cmd**. If it fails, use PowerShell to read the error. No PowerShell execution-policy change, administrator session or virtual-environment activation is required.

### macOS — Terminal

Open Terminal in the extracted project folder. Adjust the path if its name differs:

```bash
cd "$HOME/Documents/draft-kit"
python3 scripts/start.py
```

`bash scripts/start.sh` and **Start draft-kit.command** are optional shortcuts. Use Terminal if Finder blocks a downloaded shortcut.

### What you should see

The first run creates `.venv` inside the project and installs dependencies from `requirements.txt`. Later runs reuse it, installing again when that requirements file changes. This may take several minutes on first use.

```text
draft-kit — ChatGPT plan connection
Local address: http://127.0.0.1:1455
Pairing code: <your temporary code>
```

Leave this terminal open. **Ctrl+C stops the companion.** Run the same command whenever you want to use draft-kit again. There is no background service or automatic startup in the source setup. The optional desktop apps run in the tray/menu bar and can enable startup explicitly.

The companion listens only on `127.0.0.1`, on your computer. Do not expose it with port forwarding or a tunnel. Use the numeric address shown above, rather than `localhost`, because the extension permission and local host checks use `127.0.0.1`.

### Try the demo first

Append `--demo` to your startup command:

```powershell
# Windows
py -3 scripts/start.py --demo
```

```bash
# macOS
python3 scripts/start.py --demo
```

Then follow the extension and pairing steps below. Under **My context → Try a sample profile**, load the fictional sample, review and save it. Demo drafts are templates, not AI responses. Demo revisions preserve your edited text and explain that ChatGPT is required. Pasted JDs and résumé extraction work locally; job links still contact their public websites.

To switch to real AI, stop with Ctrl+C and restart without `--demo`. Refresh the extension's connection status. Saved pairing and context survive restarts.

## 4. Add the extension to Chrome

1. In Chrome, open `chrome://extensions`.
2. Turn on **Developer mode** at the top right.
3. Click **Load unpacked**.
4. Select the project's **`extension/dist` folder**, which contains `manifest.json`. Select the folder itself, not the manifest file or the outer project folder.
5. In Chrome's toolbar Extensions menu, pin **draft-kit**. Click its icon to open the side panel.

Chrome may remind you that a developer-mode extension is installed. Keep the folder in its permanent location: moving or deleting it can break the extension or change its identity. Managed work/school Chrome may block unpacked extensions; use a browser profile where your administrator allows them.

## 5. Pair and connect ChatGPT

1. In draft-kit's **Connect** tab, keep **Companion address** as `http://127.0.0.1:1455`.
2. Copy the **Pairing code** from your running terminal. Paste it into the extension and click **Pair companion**.
3. The code is single-use and expires after ten minutes. Restart the companion for a fresh code if necessary. A paired extension stays paired after restart; a second browser profile or changed extension identity needs pairing again.
4. For real AI mode, click **Continue with ChatGPT**. Sign in in the browser and approve ChatGPT plan usage if offered. Return to the extension and check the connection / model list.
5. Choose an available model. **Manage usage** opens your ChatGPT usage controls.

Each user connects their own account on their own machine. You do not configure a shared client secret or copy browser cookies. Signing in alone does not guarantee plan access; the account must be eligible and grant the required permission. Usage counts against that account's allowance or available credits. This build has no API-key billing fallback and cannot access your ChatGPT conversation history.

The plan integration follows OpenAI's [local/open-source integration guide](https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt), checked 15 October 2026. Availability and eligibility can change. A live account completing a draft is still a required beta validation step.

## 6. Add your professional context

Open **My context**:

1. Upload a **PDF, DOCX or UTF-8 TXT** résumé, or enter your name, headline, experience and writing preferences manually.
2. Review extracted facts. Fix ordering, dates and metrics; remove anything you do not want used. Name/headline and pasted fields remain editable.
3. Confirm the facts and click **Save my context**.

Uploads are limited to 5 MiB; PDFs to 20 pages. Scanned/image-only PDFs need a text-based version or pasted text; OCR is not included. Raw résumé files are processed locally and are not saved by the companion. Extracted text is unsaved until you review and save it. A new upload replaces the previous résumé facts while retaining manually entered facts. Context is capped at 60 facts / 24,000 characters, with omission notes.

## 7. Write, revise and copy

**DM:** choose **Ask an employee for a referral** or **Contact the hiring team**. Paste a JD or HTTPS public job URL and click **Write DM**. If no name is provided, the instructions call for a generic `Hi,` greeting. For a named greeting, add `Recipient name: Priya` above your pasted JD. There are no recipient-profile or conversation-context fields.

The job reader extracts one role from page text or JobPosting metadata; review its displayed summary. It cannot use your LinkedIn login, browser cookies or page JavaScript. Login walls, blocked/expired pages and multi-role listings may need a pasted JD. LinkedIn profile URLs are rejected. Up to six relevant approved facts are supplied as drafting context.

**Post:** enter an idea, choose a tone and generate. Select the suggested hashtags you want to add.

**Modify:** edit the current draft directly, then use **What should change? → Apply changes**. Your latest draft and feedback are sent together. **Restore previous draft** recovers the pre-revision version. Copy the final result and paste it into LinkedIn after review.

Drafts, JDs, prompts, feedback, selected hashtags and unsaved imports live only in panel memory. **Copy anything you need before closing the panel.** The saved professional profile persists. Generated claims and job details need your review.

## Settings, privacy and saved data

The source companion has no required `.env` file, hosted URL or API key. Default port: **1455**. To use another port, add `--port 1456` to your startup command, then change the extension's companion address to `http://127.0.0.1:1456`. The same data directory may only be used by one companion at a time.

| System | Encrypted state file | Encryption key |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\draft-kit\state.enc` | System credential store through Python keyring |
| macOS | `~/Library/Application Support/CareerComposer/state.enc` | Login Keychain through Python keyring |
| Linux (additional development path) | `~/.local/share/career-composer/state.enc` | System keyring when available; otherwise an explicitly reported private local key file under `~/.config/career-composer/keys` |

The older macOS/Linux names and `career-composer` credential service identity are retained to preserve existing beta data. An existing Windows beta state at the older Linux-style path is detected. Keep your existing encrypted state and its original key together; do not migrate by copying only `state.enc` to another machine.

On Windows/macOS, unavailable credential storage stops startup rather than silently creating a local key file. OS account permissions also matter: Unix file modes do not establish Windows ACLs. The app protects saved data from casual inspection, not malicious software running as your user.

**Clear saved profile** removes saved career facts. **Disconnect** removes local ChatGPT credentials and attempts revocation; you can also remove access in ChatGPT settings. Profile JSON exports are unencrypted files you deliberately create. To uninstall, disconnect, remove the extension, stop the companion and delete the project folder. Saved encrypted state remains at the path above until you deliberately remove it; this is separate from uninstalling the code.

The extension declares only these permissions:

| Permission | Purpose |
| --- | --- |
| `sidePanel` | Open the drafting panel |
| `storage` | Save the companion address, pairing token and first-use preference locally |
| `clipboardWrite` | Copy a draft when you click Copy |
| `http://127.0.0.1/*` host access | Contact your own local companion, including a chosen alternate port |

There are no optional permission requests, LinkedIn host permissions, content scripts or scripting permissions. In AI mode, approved context and the writing input go to OpenAI. Public job links are fetched by your companion. There is no analytics or hosted draft-kit server. See [PRIVACY.md](PRIVACY.md) for details.

### Advanced development settings

`CAREER_COMPOSER_DATA_DIR` overrides the saved-state directory. `CAREER_COMPOSER_KEY_DIR` forces a separate local key-file directory and is intended for isolated tests/headless development. It bypasses the normal OS credential store, must be outside the data directory, and should not be set for routine Windows/macOS use. These legacy variable names remain supported. Normal users need neither variable.

### Intel Mac extra setup

The pinned `cryptography` version no longer has upstream Intel macOS support or prebuilt Intel wheels. An Intel source build is **best effort**, requires extra tools, and is not verified here. Do not downgrade encryption dependencies just to avoid setup.

Install Apple's command-line tools (`xcode-select --install`) and [Homebrew](https://brew.sh/) if you do not already have them. Then, in the same Terminal where you will start draft-kit:

```bash
brew install openssl@3 rust
export OPENSSL_DIR="$(brew --prefix openssl@3)"
export OPENSSL_STATIC=1
python3 scripts/start.py
```

First setup compiles the encryption package and can take several minutes. Keep native Intel Python and Intel Homebrew consistent; do not mix architectures. See upstream [installation instructions](https://cryptography.io/en/50.0.2/installation/) and [support changes](https://cryptography.io/en/50.0.2/changelog/). The optional frozen Mac installer is a separate path in [docs/BUILDING.md](docs/BUILDING.md).

## Troubleshooting

| Problem | What to do |
| --- | --- |
| `py`, `python` or `python3` not found / wrong version | Install 64-bit Python 3.12, reopen the terminal and check its version. On Windows use `py -3.12 scripts/start.py` when several versions are installed. On macOS use the intended Python 3 executable. |
| `No such file` or `can't open scripts/start.py` | Extract the whole ZIP and open the terminal in the folder containing this README. Quote paths containing spaces. |
| Dependency installation failed | Read the pip error, check internet/proxy access and Python architecture. Retry the same startup command. Intel Macs need the extra tools above. |
| Apple could not verify an `unsigned-beta.pkg` | That is the optional unsigned installer path. See [the Mac Gatekeeper guide](docs/INSTALLING.md); the source steps above do not need a package. |
| Virtual environment broke after moving the folder or upgrading Python | Stop the companion, remove **only the project's `.venv` folder**, then rerun startup. Saved profile/credentials are stored elsewhere. |
| Keychain / Credential Locker unavailable | Run as your normal signed-in user. Unlock macOS login Keychain or check Windows Credential Manager. Remove custom keyring overrides if you configured them. Do not run as administrator to work around it. |
| Chrome cannot load the extension | Select `extension/dist`, confirm `manifest.json` exists, enable Developer mode and check whether your browser is managed. Check `chrome://version`: the extension requires Chrome 116 or newer and older builds refuse to load it. |
| Companion not reachable | Keep its terminal running; use the exact `127.0.0.1` address and matching port; click Check connection. Check local security software's loopback rules. No inbound LAN exposure is needed. |
| Pairing expired or already used | Restart the companion and pair with its newly printed code. Keep codes private. A code is consumed by its first successful pairing, so pairing a second browser profile also needs a restart. |
| Pairing refused after repeated mistyping | Ten failed code attempts lock pairing until you restart the companion. Stop it with Ctrl+C, start it again and copy the new code rather than retyping it. |
| "Pair the extension with your companion" while the panel still reads "Paired and reachable" | The extension's saved token no longer matches the companion, usually after pairing a different browser profile or moving the unpacked folder. The status line only reports that a token exists, not that it still works. Restart the companion and use **Pair again** with the fresh code. |
| Panel shows "Companion found · pairing needed" | The companion is running but this extension has no saved token yet. Pair it with the code from the terminal. |
| Another companion uses this data directory | Stop the other terminal or optional Mac app first. A leftover `process.lock` file is harmless; do not delete it while a companion is running. |
| Port 1455 already in use | Stop the old companion or start with `--port 1456` and update Connect. |
| ChatGPT is connected but no models / plan permission | Reconnect, grant plan usage if eligible, and check account/workspace access. Free-account support is not promised. Report a sanitized error if eligibility is correct but inference fails. |
| Usage limit reached | Open Manage usage; wait or adjust available allowance. The tool does not switch to API billing. |
| Résumé / job page cannot be read | Use an unencrypted text-based résumé or paste your profile/JD. Restart the companion as well as reloading the extension after updates. |
| Partial draft after an error | Review/copy the partial draft or Restore previous draft before retrying. |
| Works on Linux but fails on your Windows/Mac | Include app/Python/OS/Chrome versions and the error in an issue. Native OS/account validation is still pending; do not include credentials or résumé contents. |

## Updating

1. Copy any draft you want to keep, then stop the companion with Ctrl+C.
2. If using Git, run `git pull`. If using ZIP downloads, replace the project files in the **same permanent folder**. Avoid mixing old and new files; keep personal exports elsewhere.
3. Run your usual startup command. Dependency changes are installed automatically. If the Python environment no longer works, remove only `.venv` and retry.
4. At `chrome://extensions`, click the extension's **Reload** button and reopen its panel.

Saved profile and pairing normally survive. If the unpacked extension's folder/identity changed, pair again. Do not run the old Career Composer companion or the optional Mac background app alongside this source companion.

## Developers

Use Python 3.12 and Node.js 22+. `npm` is needed only to change/rebuild the extension.

```bash
npm ci
npm run typecheck
npm run build
npm run test:resume
```

Install test dependencies in a virtual environment and run the backend checks:

```powershell
# Windows
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.venv\Scripts\python.exe -m pytest -q
```

```bash
# macOS / Linux
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
```

After installing both dependency sets, run `npm run test:ui`. It exercises the built UI against a real demo companion with a simulated Chrome API. `npm run test:chrome` is an optional native extension smoke test after `npx playwright install chromium`; it uses a fresh browser profile. Linux may need Playwright's browser system dependencies. `COMPOSER_TEST_PYTHON` and `COMPOSER_CHROMIUM_PATH` select alternate test executables.

`extension/dist` is deliberately committed so download-only users do not need Node. Rebuild and commit it with source UI changes. GitHub Actions checks Python on Windows/macOS/Linux and builds/verifies the extension. The added workflow must run in your repository; native Windows/macOS results are not claimed from this Linux workspace.

| Folder | Contents |
| --- | --- |
| `companion/` | Local API, sign-in, protected storage, résumé/job reading, drafting |
| `extension/src/` | React/TypeScript UI |
| `extension/dist/` | Ready-to-load Chrome extension |
| `scripts/` | Source launcher, native builders, installer check and clean source packaging |
| `tests/` | Backend, UI, import and packaging checks |
| `desktop/` | Windows tray/Mac menu apps, specs and installer configuration |
| `.github/workflows/` | Source CI and manual Windows/Mac installer workflows |

See [CONTRIBUTING.md](CONTRIBUTING.md), [validation notes](docs/VALIDATION.md), [CHANGELOG.md](CHANGELOG.md) and [publishing guide](docs/PUBLISHING.md). The desktop apps are optional: Windows runs in the system tray and macOS in the menu bar. Both provide pairing, start/stop and demo controls; login startup is opt-in. Installer users follow docs/INSTALLING.md.

## Publish your copy on GitHub

Follow [publishing guide](docs/PUBLISHING.md) to upload the full project, including the prebuilt extension and workflows. Share your repository README with users; they follow sections 1–7 above. Source users run the companion locally; installer users receive a compiled package from the maintainer.

Project code is [MIT licensed](LICENSE); dependencies retain their own licenses. draft-kit is independent of LinkedIn and OpenAI. This repository is a beta, not a Chrome Web Store listing. See [validation notes](docs/VALIDATION.md) for what has actually been tested.
# draft-kit
