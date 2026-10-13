# Contributing to Lexecon

Lexecon is a local, single-organization policy and evidence workspace. Keep changes focused on that scope. A recorded decision, a valid ledger chain, a trusted signer, and actual tool enforcement are separate claims.

## Set up

Use Python 3.12 and [uv](https://docs.astral.sh/uv/) for the locked development environment:

```sh
uv sync --locked --extra dev
```

In a workspace with a read-only home cache, set `UV_CACHE_DIR` to a writable ignored directory such as `$PWD/.lexecon/cache/uv` before syncing. Dependency installation may use the network.

## Account-free checks

These commands need no administrator account or running API:

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py \
  tests/test_source_package.py tests/test_policy.py tests/test_ledger.py
.venv/bin/ruff check --select E4,E7,E9,F \
  scripts/start-local.py scripts/check-key-history.py scripts/package-source.py \
  src/lexecon/api/routers/decisions.py src/lexecon/api/routers/eu_compliance.py \
  src/lexecon/evidence_export/service.py \
  tests/test_local_launcher.py tests/test_macos_build_requirements.py \
  tests/test_key_history_guard.py tests/test_compliance_status_claims.py \
  tests/test_source_package.py
.venv/bin/python scripts/check-key-history.py .
```

The history guard checks locally reachable Git refs, staged files, and eligible worktree files for PEM private keys. It does not inspect remote-only or unreachable objects, ignored runtime data, or other secret formats. Use a clean single-branch checkout when assessing the new source history; older private refs in the original repository retain earlier key exposure.

The browser client has its own lockfile. From `frontend/`:

```sh
npm ci --no-audit --no-fund
./node_modules/.bin/tsc --noEmit
CI=true TZ=America/New_York npm test -- --watch=false --silent
CI=true npm run build
```

For API cache contract tests without a Redis daemon, use the explicitly named fake-Redis fixture selection in `tests/test_redis_cache_contract.py` and its companion API tests. These tests do not verify real Redis transport, server TTL expiry, or reconnection. Run real-service tests only with an authorized disposable service.

## Native Mac checks

The source build requires Swift 6.2+ and the macOS 26+ SDK. On a compatible Mac:

```sh
scripts/build-macos.sh --check
.venv/bin/python -m pytest -q -o addopts='' tests/test_macos_session_state.py
scripts/build-macos.sh
```

The app targets macOS 14+. Building and tests do not replace an owner-operated sign-in and export walkthrough. Do not put passwords, keys, tokens, or local `.lexecon/` data in commits, screenshots, or issues.

## Changes and releases

Keep product source, tests, lockfiles, and concise product documentation in the repository. Do not commit local runtime data, captured walkthrough media, or temporary reports. Review the final tracked-file list and rerun the history guard before release. The manual [GitHub validation workflow](.github/workflows/validate.yml) runs only when dispatched; pushing a commit does not run it. Repository-wide Ruff and mypy are not passing gates for this legacy codebase; report focused checks and remaining limits accurately.

The source packager, `scripts/package-source.py`, emits only files from a fixed commit and rejects common runtime and key paths. Its checks do not revoke historical keys or certify production readiness. Refer to [security scope](SECURITY.md) before proposing hosted use.
