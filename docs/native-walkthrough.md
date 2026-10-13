# Native walkthrough evidence

The approved native Decisions dashboard is preserved. This capture pass produced six **illustrative, offline presentation images**, not a real authenticated GUI acceptance run. Each image is an actual macOS window containing unchanged production SwiftUI views, with a visible `ILLUSTRATIVE DEMO · SAMPLE RECORDS · NO API CONNECTION` footer. The two example records explicitly use `synthetic_seed` as their origin. Chain status stays `Not checked`.

## Reproduce the presentation capture

On a Mac with Swift Command Line Tools and existing screen-capture access for the launching terminal:

```sh
python3 scripts/capture-macos-demo.py
```

A single scene can be rebuilt with `--scene 03-detail`. Output defaults to `docs/showcase/macos/`; `--output PATH` selects a different directory. The script compiles a separate ad-hoc-signed test app into a fresh temporary directory. It excludes the production `LocalAPI.swift` and substitutes `macos/Tests/OfflineAPI.swift`, whose methods always throw and create no network connection. It creates no account, password, session, signing key, or API storage. It does not change macOS permission settings.

The harness hosts `WorkspaceView` in AppKit. It assigns illustrative records directly to the workspace. In-process mouse events select the existing read row and Timeline, Analytics and Exports tabs; the resulting production views and native detail sheet are captured. No fake verification success, replacement confirmation, download notification or saved ZIP is staged. The scene images are captured by window ID without desktop, other applications, or shadow. Per-run control files remain in the isolated temporary directory. Each captured test process is terminated by its own reported PID; the harness also has a 30-second safety exit. Temporary build/log files are retained for debugging.

## Assets and evidence boundaries

All final PNGs are **2520 × 1584 pixels**, representing a **1260 × 792 point** window at 2× scale. Coordinate origin is the image's top-left. Some captures show inactive native titlebar/control styling due to foreground focus on the connected Mac; no production styling was changed to force it. `docs/showcase/macos/capture-manifest.json` records scene provenance and targets for animated cursor overlays. Keep those overlays under the same transform as the source image when zooming.

| Asset | State / observed action |
| --- | --- |
| `01-empty.png` | Empty workspace rendered with illustrative administrator identity. |
| `02-outcomes.png` | Two illustrative records assigned directly to the store: delete/deny and read/permit. |
| `03-detail.png` | In-process mouse event opened the production read detail sheet. Origin is `synthetic_seed`; chain is `Not checked`. |
| `04-timeline.png` | In-process mouse event selected Timeline. |
| `05-analytics.png` | In-process mouse event selected Analytics. |
| `06-exports.png` | In-process mouse event selected Exports; no export request or file save occurred. |

This is suitable for a labeled product design walkthrough. A film using these assets must call itself an **illustrative walkthrough with sample records**, not a recorded authenticated run. Do not animate a click on Run followed by a claimed API result, show `Chain verified`, or imply a ZIP was saved. The production API/store integration regression suite documented separately remains independent evidence and is not promoted to a GUI test claim.

## Outstanding authenticated GUI acceptance

The attempted disposable-account API setup was blocked by automatic approval review, which cited the retained restriction on creating credentials. No account or server was created. macOS Accessibility was read-only checked and found disabled; it was not changed. These are separate constraints: in-process test-app clicks work without system Accessibility, but a real authenticated API flow still needs the narrowly scoped disposable-account authorization.

After authorization, capture one real disposable session and verify: sign in; existing-policy replacement confirmation; permitted read and denied delete; inspect detail before chain verification; source-chain check; inspect updated detail; export through the native save dialog; separately rehash the saved ZIP; sign out. Keep real user credentials/storage untouched and distinguish programmatic store setup from actual UI actions. No such real GUI acceptance claim is made by this document.

An alternative does not require an assistant-created test account: the owner can run the normal launcher and enter their own password locally, then perform the same walkthrough in their chosen workspace. Passwords need not be shared in chat. A policy example replaces the policy loaded in memory only after confirmation and appends decision records, so the owner should choose a workspace where those intended changes are appropriate. This is normal product setup and use, not a temporary implementation workaround. A completed owner walkthrough must still be recorded as observed evidence; it is not implied by the available images.

The subsequent session fixes have an additional independent verification path: `tests/test_macos_session_state.py` runs compiled Swift with an in-memory URLProtocol transport. It checks eight logout, expiry, restricted-password recovery, and recoverable-error scenarios without opening a socket, creating an account, initializing API storage, or changing macOS permissions. These are state/transport regressions, not a substitute claim of GUI acceptance.
