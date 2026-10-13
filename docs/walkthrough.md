# Local walkthrough

This is the local browser workflow. The UI example produces real policy evaluations; it does not execute a tool.

## 1. Start and sign in

From the repository root, run `python3 scripts/start-local.py`. The launcher prompts for a password on first run and opens the loopback dashboard. Sign in as the local `admin` account. Data stays in the ignored `.lexecon/` directory.

## 2. Run the policy example

Select **Run policy example**. The example loads two relations: permission for the signed-in actor to `read`, and permission to use `safe_demo`. It submits a read request and a delete request through `/decide`. You should see `permit` for the read and `deny` for the delete. It calls `/decide/verify` on both responses and reports the response-to-ledger comparison. If a policy is already in memory, the UI asks before replacing it.

## 3. Inspect the record

Select **Verify Integrity** to check the local ledger hash chain. Open a decision to see its policy version, entry hash, and event fields. Decision events created by the example carry server-generated `evaluation_source: policy_engine`; `demo_requested` is a caller hint. The older `/demo/seed` endpoint creates synthetic events explicitly marked `evaluation_source: synthetic_seed`.

## 4. Export and rehash

Select **Export Audit** to save an evidence ZIP. Run `.venv/bin/python scripts/verify-evidence-zip.py /path/to/lexecon-evidence.zip` to rehash its manifest files and included events. The saved-ZIP check does not authenticate the signer or prove the entire source chain without the original ledger.

## 5. Exercise the tool boundary separately

Run `.venv/bin/python scripts/demo-proof.py`. Its disposable TestClient session obtains a permitted grant, verifies it online through the bundled reference adapter, and applies one harmless uppercase text transformation. It rejects a forged grant and an unapproved tool. That is the only executable adapter demonstrated in this repository.

See [architecture and trust boundaries](architecture.md) for the scope of these checks.
