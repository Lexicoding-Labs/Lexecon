# Lexecon Mac walkthrough — editable motion source

A [**35-second silent film**](../lexecon-macos-walkthrough-35.mp4) of Lexecon's local Mac workspace, at 1920 × 1080 on a 60 fps composition timeline. The native source recording is approximately 29.27 fps; composition frames do not add new captured motion. The edit keeps one inset native window in view while two recorded detail sheets open and close, then tours Timeline, Analytics, and Exports through a labeled editorial composite of the captured tab states. The violet, coral, and amber surround, concise captions, and pointer overlay are editorial motion; the product screens are captures of actual SwiftUI views.

**Footage boundary:** The Mac app ran in an offline presentation host with unchanged product views. The two records are illustrative `synthetic_seed` samples assigned directly to the workspace. `Ledger chain: Not checked` remains visible. The edit does not show authentication, a live policy evaluation, integrity verification, tool execution, or a saved ZIP. The captured window contains `ILLUSTRATIVE DEMO · SAMPLE RECORDS · NO API CONNECTION`; the edit places the same label below the window while a sheet or the tab composite obscures the captured footer. See [native capture notes](../../native-walkthrough.md) and the [still manifest](../macos/capture-manifest.json).

## Preview locally

Requires Node.js, npm, and installed Chromium or Chrome. From this directory:

```sh
npm ci
npm run typecheck
npm run compositions -- --browser-executable "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
npm run studio -- --browser-executable "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
```

Select `LexeconWalkthrough` in Remotion Studio. `src/LexeconWalkthrough.tsx` owns the 2,100-frame timeline. All movements are calculated from frame number, so seeking and headless still renders are deterministic. The project runs locally and makes no upload or paid service call.

Rebuild the [35-second MP4](../lexecon-macos-walkthrough-35.mp4) with `npm run render -- --browser-executable "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"`. The existing [54-second Mac film](../lexecon-macos-walkthrough.mp4) is the previous edit. [`RENDER-QA.md`](RENDER-QA.md) records checks on both encoded exports.

## Shot list

| Time | Image and action |
| --- | --- |
| 0–1.5 s | Native Decisions workspace and title. |
| 1.5–14 s | ScreenCaptureKit window recording: delete/deny detail opens and closes, then read/permit detail opens and closes. Both retain `synthetic_seed` and `Not checked`. |
| 14–17.2 s | Ledger rests; caption separates recorded evidence from chain verification. |
| 17.2–22 s | Timeline capture with two records in order. |
| 22–26.8 s | Analytics capture with one permit and one deny. |
| 26.8–32.5 s | Exports capture showing the ZIP route; no save. |
| 32.5–35 s | Closing line over the same workspace. |

`public/native/offline-ledger.mov` is the reviewed first 12.5 seconds of a window-only ScreenCaptureKit recording of the offline host. The later part of that take was excluded because its tab clicks missed after the window resized. `ledger-start.png` and `ledger-rest.png` provide matching holds around the video. Timeline, Analytics, and Exports use their corresponding original offline PNG captures in `public/macos/`. Those stills were captured through in-process clicks in the presentation host. The later tab section keeps the recorded native shell, displays the body of each corresponding capture without aspect-ratio stretching, and animates tab labels and underline matched to the captured UI. These later changes are an editorial component transition, **not** a continuous recording of tab clicks. No new product state or data is invented.

A 1280 × 870 fixed window fits the native 1280 × 869 recording without clipping. The source stills retain their 2520:1584 aspect ratio. A continuous single pointer path and short motion blur replace the earlier teleport, full-window reveals, and cursor trails. The source uses system fonts, CSS gradients, no external artwork, and no audio. [`../lexecon-macos-preview-35.png`](../lexecon-macos-preview-35.png) is a still from the new timeline.

## QA and limits

TypeScript typechecking passed. Headless Chrome rendered key frames across both recorded sheet actions, all three captured tabs, and the close. Inspection checked labels, provenance placement, window bounds, cursor placement, and frames immediately before, during, and after all three tab transitions. The pointer remains at `[143,478]` across frame 1029→1030, `[240,478]` across 1319→1320, and `[325,478]` across 1609→1610. The excluded recording portion is not used. The encoded MP4 passed a full decode check, and representative extracted frames were inspected; no full-speed playback review is claimed. The film remains an illustrative product tour; runtime and API behavior are documented separately in [release validation](../../release-validation-2026-10-07.md).
