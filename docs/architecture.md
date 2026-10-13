# Architecture and trust boundaries

![Lexecon local architecture](architecture.svg)

Lexecon is a local, single-organization policy and evidence prototype. The supported API tenant is `default`. The diagram shows the supported demonstration path rather than a deployed integration pattern.

## Decision path

1. The React dashboard or an API caller authenticates to FastAPI. `/decide` requires a session; the requested actor must match the session user unless the caller is an administrator.
2. The policy engine evaluates the requested action. If that is permitted, it also evaluates `tool:<tool_name>`. A tool without policy permission receives HTTP 403. A denied action produces a deny decision without an executable grant.
3. The decision service returns a permit or deny. A permit may include a five-minute, process-bound capability grant. Restarting the API invalidates prior grants.

The dashboard's **Run policy example** loads a small in-memory policy, calls these real endpoints for a permitted read and denied delete, and compares both response bodies with ledger entries. This UI exercise does not execute a tool.

## Enforcement boundary

`POST /capability/verify` checks the grant against the authenticated subject, action and tool scope, expiry, and current policy version. [`scripts/reference_tool_adapter.py`](../scripts/reference_tool_adapter.py) performs this online check before a harmless uppercase transformation. An external tool would need its own adapter at the execution boundary. Lexecon does not intercept arbitrary tool calls.

## Evidence boundary

`/decide` writes a server-generated `evaluation_source: policy_engine` event containing a digest of the decision response, then returns the entry hash. `/decide/verify` compares the response with that entry. The ledger links entries with SHA-256 hashes and persists them in SQLite in local mode. The dashboard's **Verify Integrity** checks the chain.

The evidence ZIP contains selected events, a verification report, a policy-hash list, a summary, and a file manifest. [`scripts/verify-evidence-zip.py`](../scripts/verify-evidence-zip.py) can rehash a saved ZIP. Rehashing is an integrity check of the exported material; a trusted signer key is needed to establish signer authenticity, and the original ledger is needed to independently establish full source-chain continuity.
