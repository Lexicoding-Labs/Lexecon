# Required dispatch pilot: scoped repair and verification

This continues Lexecon `d94a15f` without expanding the two-tool pilot. Jev's advisory comparison favored mandatory in-process dispatch for a trusted single-user read-only pilot. That advice is design input; the evidence below comes from the actual local source and tests. No broker, new platform architecture, model run or live activation was added.

## Repository identity

- Lexecon: `lexecon-release-review-2026-10-07`, branch `codex/hermes-local-integration`, starting commit `d94a15f110f1849063ef1fb41683e95c4c206ae7`.
- Isolated Hermes: `hermes-dispatch-candidate-2026-10-09`, branch `codex/required-tool-gate`. Tracked upstream source `84f87a18c0ad9f1a6d646df839110103f3204346` was imported as local root commit `ac8fa0dc9b2a5c67133975be9cd84c19e12d0f8f`; the guard is commit `c95d6b9edecf10381ff2a429e397d8009ae57e56`.
- Installed Hermes remains clean at upstream `84f87a18c0ad9f1a6d646df839110103f3204346`. The patch passed read-only `git apply --check` there; it was not applied. No remote, push or deployment is involved.

## What changed and why

The required host arms before discovery, seals the loaded plugin/handler identities, and checks the registry plus separate agent, catalog and connector paths. Missing/unarmed requirements, substituted handlers, alternate scope and unsupported tool names stop execution. The protected Lexecon handlers retain identity, final-argument policy checks and single-use capability consumption. This is a trusted-process pilot, not arbitrary-code containment. `plugins.enabled` edits alone are not instant revocation; stop/restart or rediscover the process.

The five earlier expected-permit failures were caused by the **test harness**, not a verified product authorization failure. Hermes's HomeIOGuard tracked `os.open`/`os.close` but not `os.dup`; Lexecon's descriptor-relative read uses a duplicated root fd. The harness raised `TEST BUG: untracked dir_fd in guarded filesystem I/O`, and Lexecon returned `gate_unavailable`. Tracking duplicated descriptors fixes this while a regression proves protected-home reads are still rejected after the original fd closes. No production authorization check was loosened.

Lexecon now also exports an admin-only policy snapshot and conditionally replaces/restores policy against an expected hash. Setup saves an immutable private snapshot before mutation; concurrent changes refuse restoration. Unknown responses trigger observation, not blind write retries. A rollback whose response and read-back are both lost remains an explicit unknown outcome; its backup is retained.

## Exact verification

From the Lexecon checkout:

```sh
.venv/bin/python -m pytest -q -o addopts='' \
  tests/test_policy_snapshots.py tests/test_policy.py tests/test_bound_capabilities.py \
  tests/test_security_regressions.py tests/test_decision_service.py \
  integrations/hermes/tests/test_plugin.py integrations/hermes/tests/test_owner_setup.py \
  integrations/hermes/tests/test_verify_live.py
.venv/bin/ruff check integrations/hermes --select E,F,I
.venv/bin/ruff check src/lexecon/api/models.py src/lexecon/api/routers/policy.py \
  src/lexecon/policy/engine.py tests/test_policy_snapshots.py --select E9,F63,F7,F82
```

**267 tests passed in 5.06 seconds; both focused lint commands passed.** Existing FastAPI startup and UTC datetime deprecation warnings remain.

From the isolated Hermes candidate, with `HERMES_PYTHON=/absolute/path/to/hermes-agent/venv/bin/python` (an existing interpreter):

```sh
HERMES_PYTHON=/absolute/path/to/hermes-agent/venv/bin/python \
  scripts/run_tests.sh tests/tools/test_required_tool_gate.py \
  tests/hermes_cli/test_real_home_tripwire.py -q --tb=short

HERMES_PYTHON=/absolute/path/to/hermes-agent/venv/bin/python HERMES_TEST_FILE_RETRIES=0 \
  scripts/run_tests.sh tests/tools/test_registry.py tests/tools/test_model_tools.py \
  tests/tools/test_connector_dispatch_policy.py tests/agent/test_tool_dispatch_helpers.py \
  tests/agent/test_tool_executor_checkpoint_paths.py -- -o addopts= -q

HERMES_PYTHON=/absolute/path/to/hermes-agent/venv/bin/python HERMES_TEST_FILE_RETRIES=0 \
  scripts/run_tests.sh \
  ../lexecon-release-review-2026-10-07/integrations/hermes/tests/test_api_integration.py \
  ../lexecon-release-review-2026-10-07/integrations/hermes/tests/test_required_runtime.py \
  -- -o addopts= -q
```

Results: **58 passed** (29 gate, 29 filesystem guard), **101 passed** (existing dispatch regressions), and **7 passed** (six actual API/dispatch cases, one required-startup case). The three previously unrun shared sequential/concurrent and hook-failure cases are included in the 29 passing gate cases. Independent review also reproduced **61 policy-snapshot/setup tests** and found no confirmed blocking bypass within the stated trusted two-tool boundary.

All fixture paths remain temporary. In-process API tests replace authentication with a test principal; tool gate tests inject API responses. **Real loopback login → policy setup → execution has not been run.** No account, session, live policy or installed Hermes configuration was changed. Existing prepared homes were not silently upgraded. Activation still requires explicit action-time approval and private owner credential entry.

See [the updated integration guide](../integrations/hermes/README.md) for the required launcher, verifier, snapshot rollback and trust limits. Wider platform decisions remain with the parent discussion; these checks do not establish universal agent protection or production readiness.
