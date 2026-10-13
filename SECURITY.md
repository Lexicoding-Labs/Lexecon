# Security scope

Lexecon is a local prototype for one shared organization on `127.0.0.1`. Do not expose this copy as a hosted authorization, audit, or compliance service. Global governance stores lack verified tenant isolation, the HTTP MFA flow is incomplete, and the bundled reference adapter gates only one harmless local transformation. Other tools are not automatically protected.

The API requires a local session for decisions and audit access; policy changes require an administrator. A permit requires policy permission for both the action and requested tool. Capability grants are short-lived and process-bound, so an API restart invalidates them. The ledger's hash chain detects changes relative to a trusted chain head. A downloaded evidence ZIP can be rehashed, but that alone does not prove source-chain continuity or signer authenticity.

No credentials or signing keys are supplied in the current product tree. Local setup asks the owner to choose an administrator password and creates signing material in the ignored `.lexecon/` directory. Older private Git refs in this repository retain historical signing-key exposure. Replacing `main` did not erase those objects or revoke any external trust in the old keys. Do not reuse historical key material or make the repository public without separate history and trust review.

Report vulnerabilities privately to the repository owner. Do not put credentials, private keys, or exploit details in a public issue.
