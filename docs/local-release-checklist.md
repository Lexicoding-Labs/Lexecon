# Local Mac release acceptance

The release target currently implemented is a single-organization Mac application using a loopback API. A durable implementation and reproducible tests are required; temporary credentials are a test technique, not part of the product. This checklist does not expand the supported scope into a publicly hosted authorization service.

## Permanent fixes verified on 2026-10-07

- Expired/revoked sessions return to sign-in and discard cached identity, records, pending confirmations, verification notes and export bytes.
- Local sign-out clears that state immediately and serializes server logout with other operations. A pending logout cannot overlap a new login, refresh, verification or export.
- Restricted password-change sessions can be cancelled; their expiry returns to ordinary sign-in. The username is locked during login and while the challenge is active.
- HTTP 503 remains a recoverable service error rather than being misclassified as an expired session.
- Build/toolchain and dependency failures happen before first-run account setup. Locked Python dependencies are reconciled; browser dependency changes are reconciled against the lockfile.
- Build requirements explicitly identify Swift 6.2+ and macOS SDK 26+, separately from the app's macOS 14+ deployment target.

The focused command needs no server, account, live credentials or network connection:

```sh
.venv/bin/python -m pytest -q -o addopts='' tests/test_macos_session_state.py tests/test_local_launcher.py tests/test_macos_build_requirements.py
scripts/build-macos.sh
codesign --verify --deep --strict macos/dist/Lexecon.app
```

Result: **15 pytest tests passed**, including one compiled Swift harness with **eight session-state scenarios**, and the native build passed. Historical full-suite and real API integration results remain separately identified in the [verification record](portfolio-verification.md); they are not recast as a new authenticated GUI run.

## Owner-controlled normal-use walkthrough

Run `python3 scripts/start-macos.py` from the repository root in the owner's Terminal. On first run, the owner chooses the persistent local administrator password through a hidden-input prompt. The assistant does not need to receive or store that password. Existing local data is reused without account reset.

1. Sign in normally and confirm the dashboard loads.
2. In an appropriate workspace, run the policy example and explicitly accept policy replacement if prompted.
3. Inspect the real read/permit and delete/deny records. Verify the chain separately and inspect the updated detail state.
4. Export through the native save dialog, then rehash that actual ZIP with `scripts/verify-evidence-zip.py`.
5. Sign out, confirm the sign-in screen returns, and verify sign-in works again.

These steps remain unverified as a complete authenticated GUI journey. The illustrative film is labeled accordingly. Do not use that film to claim this acceptance gate passed.

## Distribution and trust boundaries

The app is a locally built, ad-hoc-signed bundle; a Developer ID signed/notarized distribution requires the owner's Apple distribution identity and a separate release procedure. No identity, credential, OS permission or account setting was created or changed by this verification pass. The original repository's historical signing-key exposure and unknown external trust remain documented in [the key-history investigation](signing-key-history.md). The independent candidate passes its local history guard; that does not revoke a key elsewhere or rewrite the original repository.
