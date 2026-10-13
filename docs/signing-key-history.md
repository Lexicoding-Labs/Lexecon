# Historical signing keys and the release boundary

The curated candidate has independent Git history and contains no detected PEM private keys in its reachable local history, index, or eligible working files. The original Lexecon repository still has deleted private keys in its history. Deleting the files did not remove those historical versions or revoke anyone's trust in them.

## Evidence checked on 2026-10-07

The original repository is `https://github.com/Lexicoding-systems/Lexecon.git`; this investigation inspected the local checkout only, without contacting the remote or determining what remains publicly accessible.

| Evidence | Original source |
| --- | --- |
| Introduction commit | `610cf420514939ac18835b4cbc4da5a64454cbbf` |
| Deletion commit | `ae1479ab72f8923094bf607936931aafdad16abe` |
| Historical private-key paths | `lexecon_keys/private_key.pem`, `src/lexecon_keys/private_key.pem` |
| Historical public-key paths | `lexecon_keys/public_key.pem`, `src/lexecon_keys/public_key.pem` |
| SHA-256 of first public PEM file | `9eb2c96a7de192e5c82e4d7e853e1afbd48c405188928e5323e305e2006d498e` |
| SHA-256 of second public PEM file | `74155e964d07a4d2991bbd1be150dfa4e6716bc231a710d444e686bb97ddd08d` |

These are public-file hashes, not private-key material. The service's historical fingerprint convention uses the first 16 characters of the SHA-256 of public PEM bytes. They identify two distinct historical public keys. The guard reads candidate private-key matches only in memory to classify content; it never prints or copies the key bodies into reports.

The reviewed development history starts at independent root commit `1e993be562f6c5db3fb75b48dac18fd292eb243b`, rather than descending from the source repository. The publication snapshot has a separate root to omit private preparation notes and personal machine paths from outgoing history; see [snapshot provenance](current-snapshot.md). The complete development history, original checkout, and pre-existing README edit remain preserved locally.

## Repeatable release check

Run from the candidate root, using a full local repository:

```sh
python3 scripts/check-key-history.py .
.venv/bin/python -m pytest -q -o addopts='' tests/test_key_history_guard.py
python3 scripts/check-key-history.py ../lexecon
```

Expected results: candidate exit **0 / PASS**; tests pass; original exit **1 / BLOCKED**, naming the two historical private-key paths. Exit **2 / INCOMPLETE** means the check cannot establish a result, including shallow repositories. Test fixtures are synthetic PEM-shaped data, not the exposed keys. Tests cover deleted historical keys, another branch, staged content hidden by a clean working copy, unstaged/untracked keys, newline-escaped values, encrypted PEM headers, ignored runtime files, and refusal to report a shallow clone as clear.

The guard scans all objects reachable from local refs, staged blobs, and tracked/non-ignored untracked regular files. It detects JSON/string-escaped LF and CRLF PEM line endings. It excludes worktree paths with a symbolic link in any component below the repository root, including a tracked directory replaced by a link; it does not read through those links into other directories. Historical and staged blob checks remain independent of this worktree exclusion. It does not scan ignored runtime storage, inspect submodule contents, fetch remote-only refs, or inspect reflogs/unreachable objects. It detects PEM private-key containers, not arbitrary passwords, token formats, DER keys, or general secrets. Run it again immediately before staging a release and after the final commit, with no concurrent working-tree changes. A passing result does not prove the previous keys were never used or distributed.

## Local runtime boundary

The supported `python3 scripts/start-local.py` and `python3 scripts/start-macos.py` launchers set `LEXECON_DATA_DIR` to this candidate's ignored `.lexecon/` by default. They do not import keys or databases from the sibling source checkout. A new data directory generates a new local signing keypair.

`SignatureService` intentionally reloads an existing matching keypair from its configured data directory. Direct API startup without `LEXECON_DATA_DIR` uses the current working directory, and an explicit launcher `--data-dir` can select existing storage. Consequently an operator can reintroduce historical key material by copying it or selecting old storage. Do not copy historical keys or point the candidate at old signing storage. The history guard excludes ignored runtime files and cannot establish which keys a running process uses.

## Concrete publication and trust choices

The release-safe local artifact is this independent candidate, or a tracked-file archive made from its final verified commit. Keep private `.lexecon/` data, ignored files, `.git`, and generated credentials out of archives. An archive can be made with `git archive --format=tar --output=/tmp/lexecon-source.tar HEAD`, followed by inspection of its file list. Creating such an archive neither publishes it nor cleans the original repository.

Adding these changes to the existing repository is possible, but a normal commit, cherry-pick, merge, new branch, or deletion commit retains exposed ancestor objects. It must not be described as resolving the old repository's key history. Using the same GitHub destination with sanitized history would need an explicitly authorized coordinated history replacement and review of remote refs, tags, forks, cached copies, and collaborators' clones. None of those changes have been performed here. An independently published candidate can avoid copying the old history, while leaving its historical exposure unresolved elsewhere.

The owner decision that local code cannot answer is: **Were either historical keys or their public fingerprints trusted by any deployed verifier, external consumer, saved integration, or real evidence-signing workflow?** If yes, inventory those consumers and replace/revoke their trusted signing identity using the owner's deployment procedure; retain an incident note about artifacts signed with the exposed identity. Removing Git history does not accomplish that rotation. If use was confined to disposable demos, document that finding and start future demos with newly generated local material. Do not silently invalidate historical evidence or delete user data. No external consumer inspection, credential rotation, remote rewrite, or publication is claimed by this review.
