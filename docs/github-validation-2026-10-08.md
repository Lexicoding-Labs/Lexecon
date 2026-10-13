# Source release validation — 2026-10-08

This independent pass checked candidate base commit `bcb947c` without creating accounts, starting servers, using live credentials, or changing account/OS settings. Concurrent staged showcase/media edits belong to a separate workstream and were not modified or validated as final film assets here. This is evidence for preparing the source snapshot, not a claim of publication, notarized distribution, or completed authenticated GUI acceptance.

## Repeated account-free gates

Commands run from the candidate root unless indicated otherwise:

| Command | Result |
| --- | --- |
| `.venv/bin/python -m pytest -q -o addopts='' tests/test_local_launcher.py tests/test_macos_build_requirements.py tests/test_macos_session_state.py tests/test_key_history_guard.py` | **30 passed in 102.59 seconds**: 14 mocked setup/toolchain checks, one compiled Swift session-state harness, and 15 synthetic key-history checks |
| `CI=true TZ=America/New_York npm test -- --watch=false --silent` in `frontend/` | **39 tests passed across 10 suites**, 31.415 seconds |
| `./node_modules/.bin/tsc --noEmit` in `frontend/` | Passed, exit 0 |
| `CI=true npm run build` in `frontend/` | Compiled successfully; only the existing outdated Browserslist data notice |
| `scripts/build-macos.sh --check` | Passed: selected Swift 6.4, macOS SDK 27.0, arm64; deployment target macOS 14+ |
| `.venv/bin/python scripts/check-key-history.py .` | PASS: no detected PEM private keys in 657 reachable/index objects or eligible working files at check time |
| `UV_CACHE_DIR=/tmp/lexecon-github-uv-check-20261008 uv lock --check --offline` | Passed; resolved the existing 189-package lock without installation or network access |
| `.venv/bin/python -m pip check` | No broken requirements found |
| `.venv/bin/ruff check --select E4,E7,E9,F scripts/start-local.py scripts/check-key-history.py tests/test_local_launcher.py tests/test_macos_build_requirements.py tests/test_macos_session_state.py tests/test_key_history_guard.py` | All checks passed |
| `git diff --check` | Passed |

The compiled Swift harness runs eight in-memory URLProtocol scenarios: expiry during refresh/verification/export, serialized logout and subsequent sign-in, restricted password-session expiry, restricted-flow cancellation, invalid login handling, and recoverable service failure. It does not contact a socket, create a database account, or authenticate against FastAPI. Setup tests mock dependency installation and stop at the data-initialization boundary. Key-history fixtures use synthetic PEM-shaped strings in temporary Git repositories.

The first offline lock-check attempt used uv's default cache and could not access that cache inside the filesystem sandbox. Repeating the same read-only lock validation with a disposable `/tmp` cache passed; no permission or system-setting change was needed. `pip check` similarly disabled its unavailable cache and completed successfully.

## Setup and packaging review

- Python metadata and `uv.lock` agree on the `>=3.9` requirement; the package's declared CLI source exists. The environment consistency check passed. A subsequent coordinator check built the sdist and wheel with `uv --cache-dir /tmp/lexecon-uv-cache build --out-dir /tmp/lexecon-package-readiness`. Build dependencies were downloaded into the temporary cache after offline cache checks showed they were unavailable. Both distributions built successfully; setuptools reported existing license-metadata deprecation warnings. No Mac installer distribution was built.
- Browser `dependencies` and `devDependencies` exactly match the root package metadata in `frontend/package-lock.json`; frontend compilation and tests passed against the existing installed dependencies.
- Native source-build requirements now distinguish Swift 6.2+/macOS SDK 26+ from the macOS 14+ deployment target. The launcher builds before owner account setup and reconciles the locked Python environment even if an older environment exists. The normal first-run prompt remains owner-controlled.
- Root and Mac setup documentation identify the loopback API, retained local data, terminal lifetime, and source-built app boundary. The release checklist explicitly keeps the authenticated native GUI walkthrough open. No new source-snapshot blocker was found in this review.

## Remaining limits

The [normal-use GUI acceptance checklist](local-release-checklist.md) still requires the owner to sign in, run the policy example, inspect and verify real records, save/recheck an evidence ZIP, and sign out through the actual native interface. Historical full Python/security/API integration results in other reports were **not rerun** here; the full AuthService suite, live native API tests, and disposable CLI proof were deliberately excluded.

The [signing-key investigation](signing-key-history.md) still distinguishes the candidate's independent history from exposure in the original repository and unknown external trust. The guard's PASS is limited to its documented PEM/local-ref/index/eligible-file scope; it does not establish revocation, general secret absence, or remote-history cleanup. Its object count includes the index state at check time and will change as media is finalized. Run it again on the final release commit.

Developer ID signing/notarization, remote operations, and publication were not performed. Final media rendering and provenance validation belong to the media workstream. No staged media file was edited, staged, or committed by this reviewer.

Temporary logs: `/tmp/lexecon-github-safe-tests-20261008.log`, `/tmp/lexecon-github-frontend-tests-20261008.log`, `/tmp/lexecon-github-frontend-types-20261008.log`, and `/tmp/lexecon-github-frontend-build-20261008.log`.

## Manual CI preparation and package smoke check

A subsequent same-day pass inspected the prepared [workflow](../.github/workflows/validate.yml) and [contributor instructions](../CONTRIBUTING.md). The workflow has **only `workflow_dispatch`**, two Ubuntu jobs with 20-minute limits, `contents: read`, full-history checkout without persisted credentials, and pinned action SHAs. It references no repository secrets and defines no hosted macOS, publication, or deployment job. Its YAML parsed successfully with the installed PyYAML parser; structural assertions checked the trigger, permissions, job platform/timeouts, 40-character action SHAs, checkout settings, absence of secret references, and source-package regression inclusion. **No hosted workflow was run.**

The exact selected Python command was rerun locally against the prepared source-package helper and tests:

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py \
  tests/test_policy.py tests/test_ledger.py tests/test_source_package.py
```

Result: **94 passed, 37 warnings in 5.46 seconds**. The added policy/ledger tests use in-memory objects, compliance-status tests use fake services, and source-packaging tests use synthetic temporary Git repositories. None creates a user account or starts a server. Log: `/tmp/lexecon-github-workflow-pure-tests.log`.

The workflow's expanded focused Ruff command also passed:

```sh
.venv/bin/ruff check --select E4,E7,E9,F \
  scripts/start-local.py scripts/check-key-history.py scripts/package-source.py \
  src/lexecon/api/routers/decisions.py src/lexecon/api/routers/eu_compliance.py \
  src/lexecon/evidence_export/service.py \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py tests/test_source_package.py
```

The coordinator-built wheel `/tmp/lexecon-package-readiness/lexecon-0.1.0-py3-none-any.whl` was reused, not rebuilt by this reviewer. Its SHA-256 was `fac455bcf3b08193ebe40886b234570dfd0e02859d35a4ced0d9b244d0b013a7`. The reviewer installed it with `.venv/bin/python -m pip install --no-deps --no-index --target <temporary-directory>/packages <wheel-path>`, set `PYTHONPATH` to that target, and changed to the temporary directory. An explicit assertion confirmed `lexecon.__file__` resolved inside the isolated wheel target; `<temporary-directory>/packages/bin/lexecon --help` then passed. Dependencies came from the existing environment, the editable source import was not used, and the temporary target was removed afterward. No initialization, decision, or server command was invoked.

This verifies the built wheel's import/CLI entrypoint only. Source-package and wheel evidence does not replace the owner's native authenticated walkthrough, trusted-key disposition, or final-commit history check. The workflow and packaging work were still being prepared for a coordinated local commit when this addendum was written.

## Media source integration

This subsection records the earlier source-only integration. The subsequently approved 35-second MP4 and preview are now committed; see the [encoded-film review](showcase/remotion/RENDER-QA.md) for current media evidence.

The coordinator subsequently integrated the media worker's completed 35-second preview source and repeated `npm run typecheck` in `docs/showcase/remotion/` successfully. The composition declares 2,100 frames at 60 fps and preserves the previous 54-second composition separately. The media worker reported temporary still and live-preview review; the coordinator did not repeat visual review. No new MP4 was encoded by this integration. README links explicitly distinguish the editable 35-second preview from the previous 54-second export. Media and readiness changes are separate commits; the final committed source artifact must be generated after both.
