# Publish draft-kit

## Upload the clean repository

Extract the source ZIP and open its inner `draft-kit` folder. Create a public GitHub repository named draft-kit, leaving GitHub's automatic README/license/gitignore options empty. Upload the **contents** of the folder so README.md is at the root. Include the prebuilt `extension/dist`, docs and `.github/workflows`.

Using Git includes the hidden configuration files reliably. From the project root:

```bash
git init -b main
git add .
git status --short
git commit -m "Add draft-kit source and desktop installer builds"
git remote add origin YOUR_GITHUB_REPOSITORY_URL
git push -u origin main
```

Replace the remote placeholder with your repository's clone URL. If working in an existing Git checkout, keep its history and commit normally instead of reinitializing it. Review staged files before committing. Do not upload the source ZIP itself as a substitute for repository files.

The source package excludes environments, dependencies, caches, test data, historical release ZIPs and compiled installers. Keep personal résumés/exports outside the project. The prebuilt Chrome extension, tests and build tooling remain intentionally included. No fake Git history is reconstructed.

## Validate and produce downloads

1. Check **Actions → Source checks** on Windows, macOS and Linux.
2. For a Windows installer, run **Build Windows installer**. For a Mac package, run **Build macOS installers**. See BUILDING.md for native builds and signing.
3. Test the actual version/download on fresh OS accounts. Check install, tray/menu, pairing, résumé import, real ChatGPT generation/revision, restart, startup and uninstall. Automated mocked-provider tests do not establish live plan access.
4. Create a versioned GitHub Release, initially marked pre-release. Attach validated installer(s), the matching extension ZIP, checksums and INSTALL.md. GitHub source downloads also work because `extension/dist` is committed.

Unsigned installer workflows are for beta testing. Sign Windows binaries/installers for wider distribution; sign and notarize Mac packages. Installer files are release assets, not Git source files. No release, installer upload or announcement is triggered automatically by the supplied workflows.

## Invite your LinkedIn audience

Start with 5–10 testers. Share one link to the repository README with a short screen recording:

Install or run the companion → load Chrome extension → pair → connect their own eligible ChatGPT account → add résumé/pasted context → draft/revise/copy.

State the requirements: desktop Chrome, a running local companion and eligible ChatGPT Plus/Pro plan access for AI. The source path requires Python; the compiled installers bundle it. Demo mode needs no ChatGPT account. Usage limits apply, and account eligibility can change. Do not advertise universal free-account support.

Explain that résumé extraction is local, selected writing context goes to OpenAI during AI requests, and public job links contact their websites. There is no hosted draft-kit backend or LinkedIn profile scraping. Users review and manually send/post their drafts.

Enable GitHub Issues for feedback: app/OS/Python/Chrome versions, reproduction steps and sanitized errors. Never request passwords, tokens, pairing codes, callback URLs or personal résumé contents in public issues/comments.

Once setup succeeds independently for the supported systems, widen the invitation. Keep known limitations visible, retain the beta label while native/live validation is incomplete, and keep README/privacy/release notes consistent with actual behavior.

## Updates

Increment app/extension versions together, rebuild `extension/dist`, run source CI and rebuild each native installer you distribute. Users stop the companion, update source or install the new package, restart and reload the unpacked extension. There is no automatic updater in this version.
