# Bounded Hermes integration validation — 2026-10-09

Repository: isolated Lexecon candidate `lexecon-release-review-2026-10-07`, branch `codex/hermes-local-integration`, based on `fac24b3006b9e3127674e20c7b4d691cfd6b68f6`. No remote was configured. The original sibling checkout and installed Hermes source/configuration were preserved. Hermes source tested: `84f87a18c0ad9f1a6d646df839110103f3204346` (installed version 0.21.5).

## Acceptance and evidence

| Check | Evidence |
| --- | --- |
| Repeatable separate setup | Owner helper creates an isolated home, minimal two-tool profile, policy and harmless sample. Existing paths are refused; 32 mocked setup tests pass. |
| Permission before execution | Both handlers independently authenticate the configured non-admin actor, decide final arguments and consume a grant. |
| Denial/error boundaries | API, plugin and dispatcher tests cover denial, replay, policy mismatch, malformed responses, outages, expired test principal, admin/mismatched identity, altered arguments, symlinks, hardlinks, FIFO, oversized/binary files and audit failures. |
| Real framework integration | Actual Hermes plugin discovery, profile configuration, registry/direct/nested/sequential/parallel dispatch, final argument rewriting and profile separation pass. A full model or delegated agent turn is not exercised. |
| Real decision path | Actual FastAPI decision/capability routes, strict PolicyEngine, DecisionService and LedgerChain feed actual temporary file reads through Hermes dispatch. Authentication is a fixture; HTTP is in-process. |
| Independent review | Separate reviewer examined capabilities, handler/filesystem/audit boundaries, session pinning and owner setup. No unresolved blocking finding for these two tools; independent plugin/setup rerun: 87 passed. |
| Live owner activation | **Pending.** No dedicated live account/session was created, no policy replaced, no default Hermes configuration changed. A nonactive ignored sample profile was prepared. |
| Release limits | No full network/authentication proof yet, no OS sandbox, no distributed capability store, no cloud-scan conclusion, no signing-key revocation conclusion, no publishing/deployment. |

## Commands and results

From the Lexecon checkout:

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_bound_capabilities.py \
  integrations/hermes/tests/test_plugin.py \
  integrations/hermes/tests/test_owner_setup.py \
  tests/test_security_regressions.py tests/test_decision_service.py
```

**203 passed in 5.13 seconds.** Existing FastAPI startup and UTC datetime deprecation warnings remain. This integration adds no frontend/native changes, so frontend/native build evidence remains in the earlier release report rather than being represented as newly rerun.

Real Hermes checks (paths can be substituted for another installation):

```sh
HERMES_PYTHON=/absolute/path/to/hermes-agent/venv/bin/python \
  /absolute/path/to/hermes-agent/scripts/run_tests.sh \
  /absolute/path/to/lexecon/integrations/hermes/tests/test_hermes_dispatch.py \
  /absolute/path/to/lexecon/integrations/hermes/tests/test_api_integration.py \
  -- -o addopts= -q
```

**31 passed in 4.9 seconds** in the combined run (26 dispatcher tests, five API tests). After adding owner-proof orchestration coverage, the API file was rerun: **six passed in 3.1 seconds**. Final unique Hermes/API coverage is **32 passing tests**. The canonical runner needed approved temporary-directory access; test sockets are explicitly blocked. The ordinary test runner caches changed, not Hermes source or live profiles.

```sh
.venv/bin/ruff check src/lexecon/api/models.py src/lexecon/api/routers/decisions.py \
  src/lexecon/decision/service.py tests/test_bound_capabilities.py --select E9,F63,F7,F82
python3 scripts/check-key-history.py .
git diff --check
```

Focused fatal Python checks and whitespace checks passed. All new integration files also passed:

```sh
.venv/bin/ruff check integrations/hermes --select E,F,I
.venv/bin/python -m pytest -q -o addopts='' integrations/hermes/tests/test_verify_live.py
```

The owner-proof unit tests passed **11/11**. Together with the 203-test regression run and 32 Hermes/API cases, this is **246 unique passing checks**. The live verifier itself was not run; its actual-API orchestration is covered only through the test transport. The narrow PEM guard passed on 733 reachable/index objects plus eligible worktree files before this feature commit. It excludes ignored runtime data, remote-only refs, reflogs/unreachable objects and non-PEM secret formats; it is not proof of historical credential revocation.

## Reproduce or activate

See [the integration guide](../integrations/hermes/README.md) for owner setup, test commands, error handling and rollback. The nonactive local sample home is `.lexecon/hermes-workspace-2026-10-09`; it contains no session. Live activation still requires a dedicated user credential entered by the owner and a reviewed policy action. The helper refuses nonempty active policies because this API cannot export and restore the prior full policy.
