# Local candidate verification

This document records checks of the separate, curated release candidate. The product boundary is one shared organization on loopback. This is a portfolio prototype, not a hosted service or compliance certificate.

## Reproduce

From the candidate root:

```sh
uv sync --locked --extra dev
.venv/bin/python -m pytest -q -o addopts='' --disable-warnings
.venv/bin/python scripts/demo-proof.py
.venv/bin/ruff check --select E4,E7,E9,F src/lexecon/api/routers/decisions.py src/lexecon/evidence_export/service.py scripts/start-local.py
cd frontend
npm ci
npx tsc --noEmit
CI=true npm test -- --watch=false --silent
CI=true npm run build
scripts/build-macos.sh
.venv/bin/python -m pytest -q -o addopts='' tests/test_macos_smoke.py
```

For a browser walkthrough, run `python3 scripts/start-local.py` from the candidate root. Choose your own local administrator password, sign in, run the policy example, verify the ledger, inspect the two decisions, and export an evidence ZIP. Rehash the saved ZIP with `.venv/bin/python scripts/verify-evidence-zip.py /path/to/lexecon-evidence.zip` from the candidate root. For the native Mac workspace, use `python3 scripts/start-macos.py` and follow [macos/README.md](../macos/README.md).

The command-line proof uses disposable data and demonstrates a real permitted decision, a denied unapproved tool, response verification, online grant verification, a harmless text transform, and rejection of a forged grant. It needs no Redis, live model, or external account. The browser example uses real policy evaluation for permit and deny but does not execute a tool.

## Results and limits

Verified on macOS with Python 3.12.14 and the locked Python and npm dependencies on 2026-10-07:

| Check | Result |
| --- | --- |
| `uv sync --locked --extra dev` | Passed; 87 packages installed |
| Full Python suite, `pytest -q --no-cov -p no:warnings` | 1,209 passed, 8 skipped |
| Focused security regressions and supported-mode tests | 25 passed |
| `scripts/demo-proof.py` | Passed: permit, signed response, tamper rejection, unapproved tool denial, online grant check, and forged grant rejection |
| Focused Ruff `E4,E7,E9,F` on decision, evidence, and launcher files | Passed |
| Frontend `tsc --noEmit` | Passed |
| Frontend unit tests (`TZ=America/New_York`) | 39 passed across 10 suites |
| Frontend production build, `CI=true npm run build` | Passed with an outdated Browserslist data notice; no ESLint warnings |
| Headless browser walkthrough against loopback servers | Passed: bad login, login, real permit and deny, response-to-ledger comparison, integrity check, detail view, failed recheck recovery, and ZIP download |
| Saved evidence ZIP verifier | Passed: 4 manifest files and 2 events rehashed |
| Native Mac build and bundle check | `scripts/build-macos.sh`, `codesign --verify --deep --strict`, and `plutil -lint` passed on Apple Silicon; the Lexecon sign-in window was opened and visually inspected |
| Native Mac fixture regressions | 6 passed: basic flow, newest-page behavior with 201 historical decisions plus 2 new examples, and successful verification followed by HTTP 503 or disconnect during verification/refresh. The store and the same detail-view instance clear success before and after failure; the stub's ZIP bytes are only a fixture |
| Native Mac real API integration | 1 passed: compiled Swift workspace against real FastAPI/Uvicorn on loopback, isolated storage and a generated disposable administrator; sign-in, existing-policy confirmation, newest 200 of 201 historical fixture decisions, 2 real permit/deny evaluations, response comparison, chain check, ZIP export/rehash, and sign-out |
| Native dashboard design review | Restored the original dashboard hierarchy with inline example, tabs, full-width ledger, and on-demand details; reviewed light/dark sample-data previews with a fake API that cannot send requests. Glass accents primary actions, with solid content and a Reduce Transparency fallback |

The browser walkthrough used a disposable administrator and data directory under `/tmp`; its credential and generated keys are outside the repository. The native test command above now runs 7 checks (6 fixture regressions and 1 real API integration). The real API check runs the compiled workspace methods and detail state from a command-line harness, not GUI interaction. It seeds historical events directly for paging, then evaluates the two new examples through the real API. No existing user credentials or data are used. The Mac app has not been archived in full Xcode or notarized, and its authenticated UI has not yet been manually walked through against a real local administrator. The ZIP verifier rehashes the exported subset and manifest files; signer authenticity requires a trusted public key, and full source-chain continuity requires the original ledger. Global governance stores, incomplete HTTP MFA, and absence of a deployed tool adapter keep public hosting outside this candidate's scope. Repository-wide Ruff and mypy are not passing gates for this legacy codebase.

For the native regression fix on 2026-10-07, `scripts/build-macos.sh`, `codesign --verify --deep --strict macos/dist/Lexecon.app`, `plutil -lint macos/dist/Lexecon.app/Contents/Info.plist`, and focused Ruff (`E4,E7,E9,F`) on `tests/test_macos_smoke.py` and `tests/macos_live_api.py` passed. Backend and frontend suite results above are prior baseline evidence; those suites were not rerun for this native-only fix. The API returns oldest-first pages, so the app uses the reported total to find the last page; concurrent appends after that count snapshot appear on the next refresh.

The later session/setup pass ran `tests/test_macos_session_state.py`, `tests/test_local_launcher.py`, and `tests/test_macos_build_requirements.py`: **15 pytest tests passed**, including eight compiled Swift session scenarios. Those checks use in-memory responses and mocked setup operations; they create no accounts or servers. Native build, local signature validation, Info.plist lint, focused Ruff and key-history guard passed again. An independent review reran the session harness successfully. See the [local release checklist](local-release-checklist.md) for exact commands, permanent behavior changes, owner-controlled normal-use verification, and remaining distribution/trust limits.
