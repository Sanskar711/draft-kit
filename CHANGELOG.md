# Changelog

## 0.9.0 — Windows desktop and clean repository

- Added a Windows tray app, self-contained x64 per-user Inno Setup installer, native build workflow and install/runtime/uninstall check.
- Added a console worker for windowless Windows résumé imports and explicit UTF-8 worker output.
- Added opt-in Windows startup, tray pairing controls and uninstall handling; retained Mac and source setup.
- Consolidated installation/build/publishing/validation documentation under docs; removed duplicate root guides and historical debugging files.
- Added an allowlisted source packager and stricter exclusions for environments, caches, credentials and release binaries.


## 0.8.0 — Source release

- Made local Python companion + unpacked Chrome extension the primary distribution.
- Added a Python setup/start launcher shared by Windows, macOS and Linux, plus Windows command shortcuts; retained Mac shortcuts.
- Added native Windows process locking, Windows application-data paths and required OS credential storage on Windows/macOS.
- Replaced Mac-only pairing guidance with terminal pairing instructions.
- Added a full Windows/macOS README, repository publishing guide, contributing instructions and source CI.
- Retained all existing drafting/context features, branding, prebuilt extension and optional Mac desktop/build work.

## 0.7.1 — Mac packaging repair

Added an Intel static cryptography/OpenSSL build, cache bypass and source/frozen dependency checks for the reported missing OpenSSL symbol. Native Mac verification remains pending.

## Earlier development

The earlier Career Composer prototype gained résumé upload and pasted context, referral/hiring-team DMs, public job reading, post tones and hashtags, written draft revisions, profession-neutral placeholders, the draft-kit rename/theme/icons and optional Mac menu app/installer tooling. LinkedIn profile scraping and recipient/conversation capture were removed.

This source package preserves the current implementation, not reconstructed Git commit history. If you have an existing repository, commit the changes there to retain its original history.
