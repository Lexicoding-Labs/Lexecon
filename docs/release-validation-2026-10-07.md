# Independent release validation — 2026-10-07

Validated candidate commit `afeebf7` on macOS, using the existing local dependencies: Python 3.12.14, Node v26.8.1, npm 11.19.0. The candidate started clean on branch `main`. No source changes, commits, remote operations, real user credentials, or existing user data were required by this review.

## Repeated checks

Commands run from the candidate root unless the working directory says `frontend/`:

| Command | Working directory | Result |
| --- | --- | --- |
| `.venv/bin/python -m pytest -q -o addopts='' --disable-warnings --ignore=tests/test_macos_smoke.py` | root | **1,209 passed, 8 skipped**, 1,013 warnings; 25.32 seconds |
| `.venv/bin/python -m pytest -q -o addopts='' --disable-warnings tests/test_security_regressions.py tests/test_supported_mode.py` | root | **25 passed**, 222 warnings; 36.52 seconds |
| `.venv/bin/python scripts/demo-proof.py` | root | Passed: real policy permit, response verification, altered-response rejection, unapproved-tool 403, online capability check, harmless text-transform result, and forged-grant rejection |
| `.venv/bin/ruff check --select E4,E7,E9,F src/lexecon/api/routers/decisions.py src/lexecon/evidence_export/service.py scripts/start-local.py tests/test_macos_smoke.py tests/macos_live_api.py` | root | All checks passed |
| `CI=true TZ=America/New_York npm test -- --watch=false --silent` | `frontend/` | **39 passed across 10 suites** |
| `./node_modules/.bin/tsc --noEmit` | `frontend/` | Passed, exit 0 |
| `CI=true npm run build` | `frontend/` | Compiled successfully; outdated Browserslist data notice, no ESLint build failure |
| `git diff --check` | root | Passed |

Test storage is disposable. The CLI proof uses FastAPI's in-process test client and a harmless reference tool; it is neither a native GUI walkthrough nor an external tool integration.

## Native regression review

Static review of `Workspace.swift`, `DecisionDetail.swift`, and their Swift/Python test harness found both reported fixes correctly connected to the visible dashboard and detail state:

- Verification clears the prior status and explanatory note before the network await. Record refresh clears the same evidence before fetching. HTTP or transport failures leave the status as `Not checked`, while preserving the previously loaded decision records. Example execution also invalidates verification before its first mutation.
- The detail view observes the shared workspace rather than holding a copied verification string. The existing regression harness retains the same detail instance across successful verification, an in-flight recheck, and a failed recheck.
- The oldest-first API response's total determines the last 200-entry page, which is then reversed for display. The existing regression checks 201 historical decisions and the two newly created example decisions. Appends after the count snapshot appear on the next refresh, as documented; this is not a transactional snapshot across requests.

The native API tests were **deliberately excluded from this validation run** to avoid competing for loopback port 8000 with the separate native GUI walkthrough. Their earlier seven-pass evidence in `portfolio-verification.md` remains distinct: six fixture API checks and one disposable real FastAPI integration exercising compiled workspace methods. This review did not rerun or recast those results as GUI evidence. The approved dashboard structure and selective glass styling were not modified.

## Limits

- These checks support the documented local, single-organization prototype. They do not certify public hosting, multi-tenant isolation, signer authenticity without a trusted key, or complete source-chain verification from a subset export.
- The Python run completed with warnings and eight skips. Repository-wide Ruff and Python mypy are not passing release gates for this legacy codebase; only the focused Ruff command above was rerun here.
- Native GUI interaction, distribution signing/notarization, and historical signing-key disposition belong to separate workstreams. This document claims no completion of them.
- Subsequent work by other agents must be reviewed separately; this report identifies the tested base revision rather than claiming coverage of every later file edit.

Raw command logs from this session are under `/tmp/lexecon-release-{python-validation,security-tests,demo-proof,frontend-tests,frontend-types,frontend-build}.log`. They are local, temporary supporting artifacts, not published assets.
