# Privacy notes · draft-kit 0.9.0

This open-source beta runs a local Python companion on the user's computer and an unpacked Chrome extension. There is no hosted draft-kit backend. Windows/macOS native setup and real account inference still need end-to-end validation.

The desktop app starts the same loopback companion service when opened and stays in the macOS menu bar as DK, with no persistent window or Dock icon. It can copy a temporary pairing code, stop or restart the service, and copy bundled extension files into a stable Application Support folder for unpacked beta installation. Open at login is disabled by default; if you enable it, the installed app registers itself through macOS Service Management and may require approval in System Settings → General → Login Items. You can disable it from the app menu or System Settings. Quit stops the current service without changing the selected login setting. The app does not send analytics, auto-update, or upload data to a developer-controlled server. The build self-test uses temporary test state and an injected test key, not your real profile or credentials; it does not register a login item.

Uploading a résumé sends its filename and bytes to your paired local companion on 127.0.0.1. It extracts PDF/DOCX/TXT text in a temporary worker process. The original file is not saved or sent to OpenAI for extraction. Extraction has file/page/text limits and a timeout. Scanned PDF images are not processed with OCR. Extraction does not execute document scripts or macros.

Extracted text remains in the editable panel as unconfirmed context. You can remove contact details or other information you do not want used. Only after confirmation and Save my context are the facts, filename and import time stored in the encrypted profile. Pasted fields remain available, and manual facts are retained on résumé reimport.

The LinkedIn profile reader and its site/scripting permissions have been removed. The extension does not read LinkedIn profiles, inboxes, cookies or background tabs. Older saved profile provenance may remain for compatibility.

For a job link, the companion contacts the public page and checked redirects. The website sees the requested URL and your internet address. Browser cookies, pairing credentials and ChatGPT credentials are not forwarded. Pasted JDs do not contact a job website; profile links are rejected as job input.

Live drafting sends your task, selected DM purpose, writing controls, selected confirmed career facts and JD/role details to OpenAI's Responses API. Revisions also send the current edited draft and requested modifications. Imported text and draft content are treated as data in model instructions, which is not a guarantee of model obedience. Requests set store=false; OpenAI's service/account policies still govern operational processing.

Demo mode uses templates and does not call OpenAI. Public job links still require network requests in demo mode.

Chrome stores the companion address, pairing token and first-use notice preference in extension-only local storage. Writing inputs, drafts, feedback, selected hashtags and unsaved imported text remain in panel memory. The companion encrypts approved profile and ChatGPT credentials; the encryption key is kept through the OS credential store on macOS and Windows. Startup fails if that store is unavailable, unless a developer explicitly selects the test key-file override. See README.md for state paths, platform protections and the Linux fallback.

There is no analytics, advertising SDK, bulk outreach or automatic sending. HTTP access logging is disabled to avoid exposing OAuth callback codes. Worker errors do not return raw parser tracebacks or uploaded file contents.

Clear saved profile deletes stored career context. Disconnect removes local ChatGPT credentials and attempts remote revocation; app access can also be removed in ChatGPT settings. JSON exports are plain files you deliberately create and control.

The résumé worker has a timeout and input/output size limits on all platforms. Additional Unix CPU/address-space resource limits are applied where available; Windows does not provide those Unix limits. Extraction is a separate process, not a full document sandbox. Use documents you trust.

The optional Windows tray app and Mac menu app run the same loopback service without a terminal. Windows Open at login writes only the installed app path to the current user Run registry key when enabled, and uninstall removes that value. It is off by default. The Windows installer runs per user without administrator rights and leaves saved encrypted data in place on uninstall. The desktop menus copy a pairing code only when requested; they do not monitor the clipboard.
