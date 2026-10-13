# Encoded film review

## Current 35-second export

The [current film](../lexecon-macos-walkthrough-35.mp4) was rendered headlessly from the `LexeconWalkthrough` composition on 2026-10-08. SHA-256: `e7f21a297c89ed81559eed8ce82aedfa9687325e7826e59665e9d1a72e81594b`.

- MP4: H.264, 1920 × 1080, 2,100 frames on a 60 fps composition timeline, exactly 35.000 seconds, 2,970,073 bytes. The native recording source is approximately 29.27 fps; the 60 fps export does not add captured motion.
- FFmpeg decoded the complete MP4 without error. Encoded frames extracted at 0.5, 4, 9, 17.3, 22.5, 27.5, and 34.5 seconds were inspected for the native window, sheet details, tab states, captions, and closing frame.
- This review checks the encoded file and representative stills. No full-speed playback review is claimed. The film uses labeled illustrative records from an offline Mac presentation host, not an authenticated API session.

## Previous 54-second export

The deliverable was rendered from the editable Remotion project in this directory on 2026-10-07. The earlier delivered film is `../lexecon-macos-walkthrough.mp4`; SHA-256 `598463010e393c8b09cafc2f9af186a7ec59c3af42a98769135f602b6fc9e575`. The poster is a frame extracted from that encoded MP4 at 14.166667 s; SHA-256 `2b7fe39830351bc2e10f627297c6368f4c6f6e78fe5ab3f512f3a2432e659ee7`.

- MP4: 54.00 s, 1920 × 1080, 60 fps, H.264 High, 4:2:0, no audio stream, approximately 19.6 MB.
- FFmpeg decoded **3,240 / 3,240** video frames. All 3,240 decoded frame hashes were distinct, confirming moving content across the complete encode.
- Editorial and screenshot frames were visually inspected at source composition frames 150, 480, 1060, 1600, 2220, 2700 and 3060, as well as transition midpoints. Frames extracted from the encoded MP4 were inspected at 0.1, 4.75, 14.166667, 17.67, 27, 36.5, 45, 50.5 and 53.95 s. The Mac window, native labels, sample rows, source footer, typography and closing card were visible.
- The six copied PNGs match the SHA-256 values in `public/macos/capture-manifest.json`. Cursor target points stay within the screenshot stage at the highest zoom used for each related scene.
- The film contains no click on **Run policy example**, **Verify Integrity**, **Export Audit**, or **Export evidence ZIP**. It shows the read row and Exports-tab interactions observed in the offline capture harness. No `Chain verified` or saved ZIP state appears.

This is a frame-decode and visual-still review of the exported movie; no independent native media-player session is claimed. The captures are illustrative offline views, not an authenticated GUI acceptance run. Runtime test results are recorded separately in [`../../release-validation-2026-10-07.md`](../../release-validation-2026-10-07.md).
