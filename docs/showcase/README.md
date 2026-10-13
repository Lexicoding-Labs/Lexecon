# Lexecon showcase

A visual tour of the local **policy → decision → evidence** workspace, with clear provenance for each capture.

## Native Mac walkthrough

Watch the [35-second silent Mac walkthrough](lexecon-macos-walkthrough-35.mp4) or inspect its [editable Remotion source and shot list](remotion/README.md). It keeps one fixed native window in view and labels the illustrative data. The [previous 54-second edit](lexecon-macos-walkthrough.mp4) and [poster](lexecon-macos-poster.png) remain available. [Native capture notes](../native-walkthrough.md) and the [manifest](macos/capture-manifest.json) record the source images and cursor targets.

The Mac screenshots are actual production SwiftUI views in an offline presentation host, **visibly labeled illustrative**. Sample records have `synthetic_seed` origin and the ledger says `Not checked`. The film does not show authenticated evaluation, successful verification, or a saved ZIP. The [release validation](../release-validation-2026-10-07.md) documents API and frontend tests separately.

## Architecture and local proof

[See the architecture diagram](architecture.svg) ([PNG](architecture.png)) and [read its trust-boundary notes](architecture.md). The disposable [command-line proof](../../scripts/demo-proof.py) gates one harmless local transformation through the reference adapter. Saved-ZIP rehashing checks package contents; it does not by itself authenticate a signer or prove the complete source ledger.

## Archived browser walkthrough

The [earlier 30-second browser film](stipple-demo.mp4), [still preview](stipple-demo-preview.jpg), [dashboard](screenshots/stipple-02-decisions.png), [decision detail](screenshots/stipple-03-detail.png), [export after ledger check](screenshots/stipple-04-export.png), [mobile view](screenshots/stipple-05-mobile.png), and [dark view](screenshots/stipple-06-dark-decisions.png) retain their historical Stipple branding. They were captured from a real local browser run against the same API flow. [Follow the text walkthrough](walkthrough.md) or [inspect its media source](motion/README.md).
