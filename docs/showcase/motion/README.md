# Motion source

`render.py` assembles a 30-second, silent H.264 MP4 from three real local screenshots and an editorial boundary card. It crops and scales captured pixels, adds restrained editorial text, and uses no simulated product UI, stock imagery, audio, or external service. `svg-to-png.swift` makes the PNG companion to the editable architecture SVG using macOS AppKit.

The 30-second timeline is: 0–4 seconds opening statement; 4–10 seconds policy result; 10–17 seconds decision record; 17–23 seconds verification and export; 23–27 seconds enforcement and evidence boundaries; 27–30 seconds closing boundary statement. Transitions are quiet dissolves with a slight pan over captured pixels.

The archived screenshot sequence is: policy permit/deny result, an open decision record after the chain check, and the verified dashboard after evidence export. Those captures show the previous Stipple name. For a new Lexecon film, capture the same states from the current interface and update the input and output filenames before rendering. Do not mix screenshots from different builds.

From the repository root:

```sh
uv venv --python 3.12 /tmp/stipple-media-venv
uv pip install --python /tmp/stipple-media-venv/bin/python 'Pillow==12.3.0' 'imageio-ffmpeg==0.6.0'
CLANG_MODULE_CACHE_PATH=/tmp/stipple-clang-cache SWIFT_MODULECACHE_PATH=/tmp/stipple-swift-cache \
  swift docs/showcase/motion/svg-to-png.swift docs/showcase/architecture.svg docs/showcase/architecture.png
/tmp/stipple-media-venv/bin/python docs/showcase/motion/render.py --name Stipple \
  --output docs/showcase/stipple-demo.mp4 \
  docs/showcase/screenshots/stipple-02-decisions.png \
  docs/showcase/screenshots/stipple-03-detail.png \
  docs/showcase/screenshots/stipple-04-export.png
```

The script also creates `stipple-demo-preview.jpg`. Run with `--preview-only` to inspect the still composition before encoding. The Pillow and FFmpeg Python packages are used only for media production; they are not application dependencies.
