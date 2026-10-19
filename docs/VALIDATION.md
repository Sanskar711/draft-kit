# Validation — v0.9.0

The build workspace is Linux x86_64 with Python 3.12. Windows native binaries have not been compiled or executed here. The Windows installer is supplied as a native build workflow/configuration, not an already-validated download.

| Check | Result |
| --- | --- |
| Python backend, controller, build helpers and portability suite | 103 passed |
| TypeScript checking and production extension build | Passed; prebuilt extension refreshed |
| Résumé conversion, context review and permission workflows | Three groups passed |
| UI workflows with real local HTTP companion and simulated Chrome/provider | Ten groups passed |
| Source desktop self-test | Passed: PDF worker, local service, pairing and shutdown |
| Unicode résumé pipe output | Checked with Hindi/Japanese text |
| Windows worker selection, tray quit/restart state and stale-report rejection | Regression checks passed using simulated native execution |
| Source allowlist excludes local/personal/generated files | Checked with fixture archive and final source archive |
| Windows build preflight on Linux | Correctly rejects unsupported build host before native commands |
| Windows executable/installer, tray, clipboard, login registry and Credential Locker | Awaiting native build and manual OS validation |
| Windows install/runtime/uninstall CI | Supplied, not executed here; successful native build is required before artifact upload |
| Mac package/signing/notarization and native UI | Build workflow retained; not executed here |
| Real ChatGPT sign-in and completed inference | Awaiting live-account validation; provider tests use a simulated provider |

The added Windows build has two executables sharing a frozen runtime: a windowless tray app and a console worker whose console is suppressed during résumé extraction. This avoids using missing stdin/stdout streams in a windowless executable. The source worker emits UTF-8 directly. The native self-test writes a report file so the builder can verify success from the windowless executable; a leftover report cannot satisfy the check.

The Windows CI job builds, runs the frozen self-test, produces a per-user installer, silently installs it into a temporary folder with spaces, executes the installed app's self-test, and uninstalls it. These checks use injected keys, demo mode and temporary data. They do not touch real credentials or confirm UI/clipboard/startup/account behavior. The workflow has to run on Windows to validate packaging.

Existing tests cover pairing/origin/host guards, OAuth state/nonce/PKCE/JWT verification, token refresh/revocation, encrypted saved profiles, confirmed fact selection, streaming/errors, DM purposes, current-draft revisions, public job reading and résumé format/size bounds. UI tests verify profile review, résumé upload, pasted facts, job summaries/errors, tone/hashtags, feedback/restoration, copy and partial-stream recovery.

Unix locking is exercised on this host. Windows uses its native locking implementation in the source CI matrix. Windows/macOS credential-store selection and failure handling are mocked here; native keychain behavior requires manual tests. Extra Unix resource limits on the résumé subprocess are unavailable on Windows. The worker is a bounded separate process, not a complete document sandbox.

A Starlette/httpx TestClient deprecation warning remains; checks pass. A previous native Chromium launch was blocked by this workspace. Native Chrome rendering, live public-job compatibility, all résumé layouts, managed-browser policies and real ChatGPT plan eligibility remain manual beta checks.

The earlier Mac repairs for Tkinter, a delegate signature and Intel OpenSSL library collisions are retained. Intel macOS is best effort because the pinned encryption dependency dropped upstream support. The unsigned installer warning is a signing/notarization issue, separate from runtime import failures.

The source package contains no Git metadata, installed dependencies, local state, credentials, historical release archives or compiled installers. All current source, tests, icons, notices, workflows, specs and prebuilt extension remain. Duplicate root guides were consolidated into README.md and four docs files. No repository, installer build or public release was pushed from this workspace.
