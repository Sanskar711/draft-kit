# Contributing

Use the source setup and development commands in README.md. Keep changes focused, explain the user-visible behavior, and include relevant verification in pull requests.

Run Python tests, TypeScript checking, the extension build, résumé import checks and UI smoke checks before proposing behavior changes. New tests should cover actual failure modes rather than repeat the implementation. Source CI targets Windows, macOS and Linux. Native OS credential-store checks and real ChatGPT sign-in need manual validation.

Commit `extension/dist` whenever extension sources change: ZIP-download users load this folder directly. Keep package.json, package-lock.json, the manifest, companion health version and test manifest version in sync when releasing.

Do not commit `.venv`, node_modules, test state, saved profiles, résumés, OAuth credentials, pairing codes, callback URLs or personal exports. Use fictional fixtures. Do not add LinkedIn scraping or automatic sending to the existing flow. New Chrome permissions need a concrete feature reason and matching README/privacy changes.

For native Windows/Mac work, see docs/BUILDING.md. The main source launcher must remain usable without desktop dependencies on Windows and macOS.

Project code uses the MIT license; contributions are under that license. Preserve third-party notices.

Use scripts/package_source.py to prepare clean source archives. Generated installers and local environments are not repository files. Keep installer changes consistent with docs/BUILDING.md and docs/INSTALLING.md.
