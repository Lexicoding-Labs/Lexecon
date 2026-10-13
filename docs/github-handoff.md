# GitHub source handoff

The candidate is an independent repository with preserved source attribution and no configured remote. The original checkout and its existing changes remain separate. GitHub preparation does not publish the candidate or resolve trust in the historically exposed signing keys.

## Reproduce a fixed source snapshot

Finish and commit the intended source and media changes first. Then run from the candidate root:

```sh
git status --short
git rev-parse HEAD
python3 scripts/check-key-history.py .
python3 scripts/package-source.py --commit HEAD --output /tmp/lexecon-source-release
```

Choose a new output directory for each release. The packager refuses to overwrite an existing artifact. It reads only the selected committed tree, leaving the index and working tree untouched. A dirty tree is allowed for parallel work, but those changes are explicitly **not** part of the artifact. Resolve that difference before calling a snapshot the final release.

The TAR has a single `lexecon-<commit>/` prefix, deterministic timestamps and modes, and exactly the committed regular files. Its adjacent JSON records the full commit, Git tree, archive SHA-256, and each file's SHA-256. Symbolic links, submodules, common runtime/credential paths, and detected PEM private keys are rejected. `.git` ancestry and untracked/ignored files are never included. The PEM/filename checks are bounded checks, not a comprehensive secret audit. Run the separate history guard as well.

The archive is the complete source checkout, including committed native and browser sources and showcase assets. A Python wheel is a separate backend/CLI package; it is not a Mac installer or a replacement for the full checkout.

## Validation and future CI

See [the validation evidence](github-validation-2026-10-08.md), [contributor commands](../CONTRIBUTING.md), and [local Mac acceptance](local-release-checklist.md). The GitHub workflow is manual-only, uses pinned action commits and read-only repository access, and requests no deployment secrets. It is prepared locally; no hosted run is implied. A repository owner can review GitHub Actions availability and billing before choosing to run it.

## Cloud scan target

Give the scanner the fixed artifact and adjacent manifest when it supports local uploads. If it requires a connected repository/provider/ref, this candidate currently has no such remote ref. Do not silently scan the old upstream checkout: it has different source and exposed ancestry. Publication or a remote source transfer requires an explicitly authorized destination and transfer method. Record the scanner's resolved commit or artifact hash, scope, and exclusions with its findings, then reproduce each material claim and verify fixes against the resulting revision.

The connected cloud scanner's preflight on 2026-10-08 found that its launch API requires a connected GitHub repository and matching cloud environment; it accepts no local artifact, branch, or explicit commit argument. The existing `Lexicoding-systems/Lexecon` repository was private and archived, and its `main` branch is not this independent candidate. Provider usage also reported unavailable access despite a contradictory remaining-credit figure. The source artifact therefore serves as a provenance checkpoint, not an uploadable target for that API. A separately authorized remote transfer and resolved scanner access are needed before that provider can scan the final candidate. Neither a push nor an unarchive was performed.

The source artifact carries no repository history, so a source scan cannot validate historical revocation or clean up an old remote. The [signing-key investigation](signing-key-history.md) records that separate boundary. No external credential use or trust was established by the local investigation.

## Remaining release gates

- Owner-operated authenticated native walkthrough using the ordinary local launcher; no password needs to be shared with an assistant.
- Developer ID signing/notarization for downloadable Mac distribution; the current local build is ad-hoc signed.
- Explicit destination/history decision before any push, with owner disposition of historical external signing-key trust.
- The approved 35-second film, preview image, and editable Remotion source are included in the candidate. The previous 54-second export is retained. See the [encoded-film review](showcase/remotion/RENDER-QA.md) for file hashes and validation limits; the illustrative footage does not establish authenticated GUI acceptance.
- Final source artifact/hash and the separately requested cloud scan against that exact state, after any further changes.

These gates prevent claiming a publicly deployed production authorization service or a signed consumer Mac release. The implemented, tested scope is the local, single-organization policy and evidence workspace.
