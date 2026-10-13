# Security scope

Lexecon is a local portfolio prototype for one shared organization on `127.0.0.1`. Do not expose this copy as a hosted authorization, audit, or compliance service. There is no verified tenant isolation for global governance stores, complete HTTP MFA flow, or enforcement adapter for real external tools. The reference adapter only gates a harmless local text transformation.

The API requires local sessions for decision requests and audit access. Policy changes require an administrator. A policy must permit both the action and requested tool before a capability grant is issued. Grants are process-bound and expire; restarting the API invalidates them. The dashboard can compare a decision response to its ledger record and check the source ledger hash chain. A downloaded evidence ZIP can be rehashed, but that check alone does not prove source-chain continuity or signature authenticity.

No credentials or signing keys are supplied with this review copy. The local setup asks the owner to choose an administrator password and generates local signing material in the ignored data directory. The source project's earlier Git history contained now-deleted signing-key files; this fresh-history copy excludes them. Whether any old key was used outside the demo remains an owner investigation. Do not reuse that key material.

If you find a vulnerability, contact the repository owner privately. Do not put credentials, private keys, or exploit details in a public issue.
