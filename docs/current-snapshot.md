# Current source snapshot

This branch contains the reviewed local workspace through development commit
`900741699cda1fbce44e6d30d4a7bc0559decd29`. Runtime code, tests, dependency lockfiles,
UI sources and reviewed demonstration assets are unchanged from that input.
Documentation was adjusted for publication, and the manual workflow fetches only
its selected branch history to avoid importing unrelated legacy branches.

## Validation available

The October 11 offline run passed 326 unit and in-process API tests. It includes
password-rotation/session-race regressions, failed and uncertain ledger writes,
capability verification, and asynchronous cache result handling. Redis behavior
uses explicitly named dependency fakes. No real Redis transport, expiration,
reconnect or performance result is claimed. The model-driven Hermes audit and
live deployment remain unverified. Existing UTC datetime warnings and broader
legacy lint limitations remain; selected checks are documented in CONTRIBUTING.md.

These results apply to the unchanged development source, not to a new remote CI
run. This branch's GitHub validation workflow is manual and does not run on push.
The source guard must pass before any new validation claim. Tests do not establish
production readiness, tenant isolation or regulatory certification.

## Source provenance and exclusions

This is a source snapshot assembled for cross-machine development, not a rewrite
of the original repository's branches. Its root commit records assembly of the
snapshot; it does not claim that the committer originally authored every file.
Existing code copyright/license notices remain intact. The original development
commits and contributor authorship are preserved in the local source history.
The input revision above is a provenance identifier, not an ancestor available
through this snapshot branch.

Private audit preparation notes, personal absolute machine paths, local validation
logs, database state, sessions, signing keys, credentials, dependency directories,
and generated runtime files are excluded. Historical signing-key exposure in the
original repository is not repaired by this independent branch. See
[the signing-key boundary](signing-key-history.md).

## Get this version

Clone only the publication branch to avoid unrelated legacy history:

```sh
git clone --single-branch --branch publish/local-workspace-2026-10-13 https://github.com/Lexicoding-systems/Lexecon.git
cd Lexecon
uv sync --locked --extra dev
```

For an existing clone, fetch and switch to the named branch without resetting local
work. The publication does not merge into or replace `main`. Use the README's local
launchers only after reviewing their dependency-installation and initial-account
setup behavior. The existing repository is private, so another machine still needs
its own authorized GitHub access.
