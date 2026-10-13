# Lexecon — native walkthrough storyboard

> **Historical 54-second plan.** The current editable [35-second motion preview](remotion/README.md) uses one fixed native window and updated timing. The existing 54-second MP4 remains available; this planning document is retained to show the original capture contract and constraints.

**Production status:** The finished illustrative film, editable source, and exact transcript are in [remotion/](remotion/README.md). The conditional authenticated scenes below remain a planning reference; no real-session evaluation, successful chain check, or ZIP save was captured.

Production plan for a **54-second, 1920 × 1080, 60 fps** silent Remotion film. This is preproduction, not a claim that the screenshots or GUI checks below already exist. Use the current native Lexecon build and actual captures from one disposable local session. Preserve the approved Decisions dashboard and restrained Liquid Glass accents.

**Current capture handoff:** the authenticated-session capture was blocked by automatic approval review pending explicit permission for a disposable test account. The available native assets are unchanged production views in a zero-network harness, visibly labeled **Illustrative demo / Sample records / No API connection**. They are suitable for a design/workflow film, not evidence that the displayed example was evaluated or verified. Until real-session captures are available, adapt scene 02 to explain the example control, scene 03 to describe sample permit/deny records, scene 05 to explain the verification control with **Not checked**, and scene 06 to show the Exports tab. Do not create a successful verification, save dialog, saved-ZIP confirmation, or `policy_engine` label that was not captured. The real API regression evidence is separate. Read `docs/native-walkthrough.md` and the capture manifest when available before producing the film.

## Story and visual direction

The viewer should understand one complete path: **evaluate → inspect → verify → export**. The app remains the subject. The opening and close supply the brand; the middle demonstrates actual controls and outcomes.

Use forest `#245E4D`, deep ink `#111D19`, cream `#F3F5EF`, and pale sage `#C9DED2`. Keep product screenshots unchanged. Animate broad, low-contrast radial gradients behind the app, with slow position shifts and a 24-second color cycle. Avoid placing animated highlights over evidence text. Reuse the real app window and its native chrome; do not draw a replacement interface or add invented navigation.

Use the local system sans serif for editorial titles and a local monospace for small technical labels. At 1080p, hero titles are 120–152 px, scene headlines 72–88 px, and essential supporting text 42–48 px. Keep key text inside a 120 px horizontal / 100 px vertical safe area. Limit a scene to one headline and one short supporting statement. Product evidence receives its own readable close-up rather than asking the viewer to read an entire scaled dashboard.

Start typography quickly: 12–18 frame masked word reveals with 24–40 px travel, 5-frame staggering, and ease-out settling. Hold the completed phrase long enough to read. Use gentle camera moves over screenshots, normally 1.00–1.16× and up to 1.30× for evidence details. Keep native controls crisp and avoid overscaling screenshots beyond their available pixels.

## Exact timeline

The seven source scene durations sum to **3420 frames**. Six 30-frame overlaps yield **3240 frames / 54 seconds**. In the table, end times are exclusive. Each scene is a separate authored sequence and a separately registered connected composition.

| Scene / component | Global frames / time | Local duration | Image and action | Editorial copy and focus |
| --- | --- | --- | --- | --- |
| 01 `Opening` | 0–300 / 0–5 s | 300 | Cream/forest gradient; actual dashboard window rises subtly into the lower-right background. No cursor. | Large `Lexecon.` then `Decisions, with evidence.` Small `Native Mac workspace`. Three quick word reveals, then settle. |
| 02 `RunExample` | 270–810 / 4.5–13.5 s | 540 | Signed-in empty dashboard. Local f90–140: cursor moves to **Run policy example**; f150 click. Crossfade to real post-run capture after f180. If actual session requires replacement confirmation, include its real capture and **Replace and Run** action; do not imply the alert was absent. | `Start with a policy.` Supporting `A permitted read. A denied delete.` Keep `Example evaluates policy; no tool executes.` visible for at least 3 s near the end. |
| 03 `ReadOutcomes` | 780–1380 / 13–23 s | 600 | Post-run dashboard with two real records. Local f30–120: smooth zoom into ledger; f170–230: cursor indicates the deny outcome, then f280–340 indicates permit. No click unless opening a record. Highlight labels using restrained external callout lines. | Headline `Two outcomes. One clear record.` Callouts `Read → Permit` and `Delete → Deny`, staggered by 36 frames. End with `Evaluated by the policy engine.` |
| 04 `InspectDecision` | 1350–1950 / 22.5–32.5 s | 600 | Local f40–90: cursor moves to the actual read/permit row; f100 click; after f120 show its real detail sheet. Zoom toward action, actor, evaluation source, decision ID and **Ledger chain: Not checked**. Keep the latter legible. Local f500–540: move to **Done**, f545 click; return to dashboard. | `Inspect the decision.` Supporting `Action, actor, origin, and ledger evidence.` Then replace supporting line with `Chain integrity is a separate check.` Do not call a policy result a verified ledger. |
| 05 `VerifySourceChain` | 1920–2460 / 32–41 s | 540 | Dashboard before verification. Local f40–95: cursor moves to **Verify Integrity**; f110 click. Show actual resulting **Chain verified** capture only after the corresponding successful check. Move camera from control to status strip. Optional real open detail after verification may replace final 2 s if readable. | `Check the source chain.` Supporting `A point-in-time integrity check.` No lock icon or language implying trusted identity, compliance, or automatic tool enforcement. |
| 06 `ExportEvidence` | 2430–2910 / 40.5–48.5 s | 480 | Local f35–80: move to **Export Audit**; f90 click. Show real native save dialog, then actual saved confirmation. Do not add a fake download toast. Crop or omit personal filesystem paths. If save capture is blocked, show actual Exports tab and label it `Export workflow`; do not claim a saved ZIP. | `Take the evidence with you.` Supporting `Events + manifest, in a ZIP.` Final line `Rehash the saved package.` This describes the separate verifier, not a claim that saving authenticates the signer. |
| 07 `Closing` | 2880–3240 / 48–54 s | 360 | App window recedes gently into ink/forest gradient. Cream typography slides upward in two short beats, then still hold for final 2 s. No cursor. | `Lexecon.` / `Policy → decision → evidence.` Footer `Local portfolio prototype · One shared organization`. Optional launch command `python3 scripts/start-macos.py` on its own readable 42 px line. |

Scene start frames are **0, 270, 780, 1350, 1920, 2430, 2880**. Do not subtract transition durations twice. Use a 30-frame soft dissolve with a small shared camera drift between product scenes. Opening/closing may use a directional gradient wipe, but never a flash. Preserve spatial continuity so Verify and Export remain where the viewer learned them.

## Cursor and callout rules

The cursor is an editorial overlay following the real interaction sequence. Use a 28–34 px Mac-style pointer with subtle shadow, never a giant hand. Each movement follows a smooth cubic path for 45–60 frames, decelerates at the target, holds 10–15 frames, then clicks. Click feedback is a 24-frame expanding ring from 8 to 32 px with opacity fading to zero; pointer scale briefly dips to 0.92 over 6 frames. Use no persistent halo.

Track cursor points in **source screenshot coordinates**, with `{width, height, crop}` stored alongside each capture. Transform the cursor and callout anchors with the same screenshot camera transform so the pointer stays attached to the real control during zoom. Never guess a target coordinate from a different window size. Hide the cursor during a cut that changes window geometry. Prefer line endpoints outside controls and readable text beside the crop, not overlays that obscure labels.

Required semantic targets, to measure from the final captures:

| Target ID | Real control or evidence anchor | Used in |
| --- | --- | --- |
| `runExample` | Center of **Run policy example** button in inline card | Scene 02 |
| `replaceAndRun` | Center of **Replace and Run** in real confirmation, if present | Scene 02 |
| `denyOutcome` | Deny badge in delete row | Scene 03 |
| `permitOutcome` | Permit badge in read row | Scene 03 |
| `readRow` | Action/actor area of read row, safely away from other controls | Scene 04 |
| `detailChain` | **Ledger chain** value in real detail sheet | Scene 04 / optional 05 |
| `detailDone` | **Done** button of native detail sheet | Scene 04 |
| `verifyIntegrity` | Center of **Verify Integrity** in page heading | Scene 05 |
| `chainStatus` | **Chain verified** in dashboard status strip | Scene 05 |
| `exportAudit` | Center of **Export Audit** in page heading | Scene 06 |
| `save` | Native save dialog confirmation, if captured | Scene 06 |

## Capture contract and truthfulness

Assets belong under `docs/showcase/macos/`; copy or link the approved assets into the Remotion project's `public/macos/` for deterministic local rendering. Final filenames and coordinates are pending the native capture agent. The semantic states needed are:

1. Signed-in empty Decisions dashboard, no credential fields.
2. Real post-example dashboard with read/permit and delete/deny rows.
3. Read/permit detail before chain verification, showing **Not checked**.
4. Dashboard after successful source-chain verification.
5. Optional matching detail after chain verification.
6. Real export save dialog and saved confirmation, or an explicitly limited Exports-tab fallback.

Record each asset's filename, pixel dimensions, window bounds, build commit, state, and whether it came from interactive GUI control or a workspace rendering harness. Keep generated disposable usernames generic; exclude passwords, bearer sessions, signing material and personal paths. An API test or programmatically rendered view does not establish a manual GUI walkthrough. If real interactive capture cannot be completed, the film description must say exactly which states are rendered from real API responses and which GUI actions remain unverified.

Film description: **“Edited walkthrough of Lexecon's local Mac workspace. Captured product states with animated cursor, zoom, and callout overlays; timing is condensed.”** Amend this if capture provenance requires narrower wording. Do not present composited timing as an uninterrupted screen recording.

Only use `Chain verified` from a successful check in the same session. A new evaluation or refresh invalidates earlier verification. Do not juxtapose an earlier success with later unverified records. The example evaluates policy and records evidence; no external tool runs. Saved ZIP rehashing checks package contents, not trusted signer identity or the complete source chain. The app is a local prototype/source build, not a notarized commercial release or production authorization service.

## Remotion implementation handoff

Reuse an existing Remotion project if one exists; the current `docs/showcase/motion/` is a Python renderer, not a Remotion project. A new `docs/showcase/remotion/` folder is appropriate after inspecting it for existing user work. Do not delete the earlier browser film or pretend its Stipple captures show the current native app.

Suggested structure:

```text
src/Root.tsx                    master + seven connected scene registrations
src/LexeconWalkthrough.tsx     explicit TransitionSeries, inline durations
src/scenes/Opening.tsx
src/scenes/RunExample.tsx
src/scenes/ReadOutcomes.tsx
src/scenes/InspectDecision.tsx
src/scenes/VerifySourceChain.tsx
src/scenes/ExportEvidence.tsx
src/scenes/Closing.tsx
src/components/CaptureStage.tsx
src/components/AnimatedCursor.tsx
src/components/Callout.tsx
src/components/GradientBackdrop.tsx
public/macos/                  approved actual captures and coordinate metadata
```

Register master `LexeconWalkthrough` at 1920×1080 / 60 fps / 3240 frames. Register each scene at its matching duration and props in a `Lexecon-Scenes` folder. Author each independently editable scene/layer explicitly; do not generate the story via one array map. Use `useCurrentFrame()`, `interpolate()` and `spring()` for all motion; no CSS animations, transitions, wall-clock timing or random values. Reference local assets with `staticFile()` and use the image component supported by the installed Remotion version. Keep all rendering local; do not request music, voice generation or paid services. A silent version should stand on its own.

Deliver `lexecon-macos-walkthrough.mp4` (H.264, 1920×1080, 60 fps, 54 seconds), a 1920×1080 poster from the actual ledger scene, editable source, lockfile, render command, and a short text transcript reproducing the film's claims. Update showcase links only after the new artifact is rendered and inspected. Keep historical browser artifacts labeled as historical.

## Render acceptance

- Inspect stills at frames 150, 480, 1060, 1600, 2220, 2700 and 3060, plus each overlap midpoint and click frame.
- Check all cursor endpoints against screenshot coordinates at both camera extremes.
- Verify no clipped type, low-contrast essential copy, personal data, mismatched native states or stale chain success.
- Open the exported movie and check duration, dimensions, frame rate, start/end frames and smooth transitions. A frame render alone is insufficient evidence that the MP4 is correct.
- Record exact build/capture provenance, render command and output verification. Claim GUI execution only to the extent actually observed.
