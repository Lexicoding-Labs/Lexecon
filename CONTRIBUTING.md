# Contributing to Lexecon

Lexecon's supported product is a local, single-organization policy and evidence workspace. Keep changes focused on that boundary and preserve the documented distinction between recorded decisions, ledger integrity, signer trust, and actual tool enforcement. Avoid claims that a source build or passing tests establish hosted-service readiness or regulatory compliance.

## Local checks without accounts or servers

Install the locked development dependencies using Python 3.12 and `uv`:

```sh
uv sync --locked --extra dev
```

This synchronizes `.venv` and may download packages. The following selected checks need no local administrator, signing identity, live service, or network connection once their dependencies are installed:

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py tests/test_source_package.py \
  tests/test_policy.py tests/test_ledger.py
.venv/bin/ruff check --select E4,E7,E9,F \
  scripts/start-local.py scripts/check-key-history.py scripts/package-source.py \
  src/lexecon/api/routers/decisions.py src/lexecon/api/routers/eu_compliance.py \
  src/lexecon/evidence_export/service.py \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py tests/test_source_package.py
.venv/bin/python scripts/check-key-history.py .
```

The tests use mocks, in-memory policy/ledger objects, and synthetic temporary Git fixtures. The history guard is a narrow PEM check; read its reported exclusions. It must have full local history and does not clear historical exposure or trusted keys elsewhere.

Browser checks run from `frontend/`:

```sh
npm ci --no-audit --no-fund
./node_modules/.bin/tsc --noEmit
CI=true TZ=America/New_York npm test -- --watch=false --silent
CI=true npm run build
```

Node 26.8.1 and uv 0.12.22 match the prepared workflow. Dependency installation may use the network; these test/build commands do not launch the app's API or create user accounts. Repository-wide Python Ruff/mypy are not claimed as passing gates; use the focused checks above and targeted regressions appropriate to a change.

## Offline Redis dependency contracts

Redis is optional for the selected API behavior checks. The `redis_unavailable`
fixture is explicitly requested by the four status/compliance/workflow tests that
previously contacted Redis implicitly. It substitutes only the Redis client
factory: a synthetic `PING` raises `redis.ConnectionError`, exercising the normal
cache-disabled path. The fixture is not automatic, restores the cache singleton
and client factory after each test, and changes no application setting or network
permission. Authentication, policy, decision, ledger and response assertions still
run against their real in-process implementations.

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_redis_cache_contract.py \
  tests/test_api.py::TestHealthEndpoints::test_status \
  tests/test_api.py::TestIntegrationWorkflows::test_complete_governance_workflow \
  tests/test_api_additional.py::TestComplianceMappingEndpoints::test_get_compliance_statistics \
  tests/integration/test_api_integration.py::TestHealthEndpoints::test_status_endpoint_returns_metrics
```

`test_redis_cache_contract.py` uses a synthetic in-memory Redis client for cache
hits, serialization, TTL argument forwarding and failure injection. It verifies
that asynchronous handlers complete before their results are cached, synchronous
handlers keep working, handler exceptions are not cached, authenticated requests
remain required on protected cache hits, and arbitrary guard refusals still
propagate. No test in this selection needs a Redis daemon or starts a socket
server. Keep any external offline network guard in place.

These checks are **unit and in-process API contracts with fake Redis**, including
those under `tests/integration/`. They do not verify Redis transport, server TTL
expiration, reconnect behavior, deployment settings, or performance. A genuine
Redis integration run requires a separately authorized disposable Redis process
and restricted local transport; do not point these tests at an existing service
or relax a network guard to obtain a passing result.

## Native Mac checks

Building the native app requires Apple developer tools with Swift 6.2+ and the macOS 26+ SDK. The built app targets macOS 14+. On a compatible Mac:

```sh
scripts/build-macos.sh --check
.venv/bin/python -m pytest -q -o addopts='' tests/test_macos_session_state.py
scripts/build-macos.sh
codesign --verify --deep --strict macos/dist/Lexecon.app
```

The session-state test uses URLProtocol responses entirely in memory; it creates no account and starts no socket server. Native GUI acceptance is separate: the owner can follow the [normal-use checklist](docs/local-release-checklist.md) and enter their own password in the normal local interface. Never request passwords in issues or pull requests. Running the complete Python suite, `tests/test_macos_smoke.py`, or `scripts/demo-proof.py` may create disposable local accounts and/or servers; these are intentionally outside the account-free command set.

## Prepared GitHub workflow

[Manual source validation](.github/workflows/validate.yml) has only `workflow_dispatch`. It does not run automatically when the repository is published, pushed, or receives a pull request. An authorized maintainer may explicitly start it in GitHub Actions after considering the repository's runner usage and billing settings. No hosted execution is claimed by this preparation.

The workflow uses pinned action commit SHAs, read-only repository permissions, full-history checkout, no persisted checkout credentials, and no repository secret references. Its two bounded Ubuntu jobs run the selected Python regressions/history guard/focused lint, build a wheel and invoke its installed CLI with `--help`, and run browser tests/types/build. Installing the wheel replaces only the disposable runner's editable package. The workflow does not initialize Lexecon data, create an administrator, start the API, publish artifacts, deploy, or use a hosted macOS runner. Native gates remain local.

## Changes and release boundaries

Use a focused branch and describe the user-visible problem, resulting behavior, relevant test results, and remaining limits in the pull request. Add focused regressions for security boundaries and asynchronous state failures. Preserve existing user work and keep real `.lexecon/` data, private keys, tokens, and generated credentials out of commits and screenshots.

Before preparing a release, rerun the key-history guard against the final commit. A normal merge into the original repository retains its historical private-key objects; consult the [signing-key investigation](docs/signing-key-history.md) before choosing a publication path. Publication, history replacement, external trust changes, and Developer ID signing/notarization require separate owner decisions and are not performed by this workflow.
