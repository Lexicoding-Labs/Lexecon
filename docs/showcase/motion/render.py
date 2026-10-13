#!/usr/bin/env python3
"""Render a 30-second silent local demo from real application screenshots.

Dependencies (temporary environment is fine): Pillow and imageio-ffmpeg.
Run from the repository root after the final screenshots exist:

  python docs/showcase/motion/render.py --name PROJECT_NAME \
    docs/showcase/screenshots/stipple-02-decisions.png \
    docs/showcase/screenshots/stipple-03-detail.png \
    docs/showcase/screenshots/stipple-04-export.png

The source images are scaled/cropped for composition; it never draws simulated UI.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import subprocess
import sys

from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

SIZE = (1600, 900)
FPS = 20
SECONDS = 30
INK = (25, 40, 36)
BLUE = (35, 95, 77)
MUTED = (75, 94, 85)
PAPER = (245, 246, 242)
WHITE = (255, 255, 255)
PALE = (232, 243, 234)
SKY = (168, 222, 181)
FONT_ROOTS = [
    Path('/System/Library/Fonts/Supplemental'),
    Path('/usr/share/fonts/truetype/dejavu'),
]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (['Arial Bold.ttf', 'DejaVuSans-Bold.ttf'] if bold else
                  ['Arial.ttf', 'DejaVuSans.ttf'])
    for root in FONT_ROOTS:
        for name in candidates:
            path = root / name
            if path.exists():
                return ImageFont.truetype(str(path), size)
    return ImageFont.load_default(size=size)


def smooth(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def visibility(t: float, start: float, end: float, fade: float = 0.6) -> float:
    return smooth((t - start) / fade) * smooth((end - t) / fade)


def text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], value: str,
         size: int, color: tuple[int, int, int], bold: bool = False) -> None:
    draw.text(xy, value, font=font(size, bold), fill=color,
              stroke_width=0, anchor='lt')


def rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int],
            fill: tuple[int, int, int], radius: int = 20) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def base(name: str, dark: bool = False) -> Image.Image:
    im = Image.new('RGB', SIZE, INK if dark else PAPER)
    d = ImageDraw.Draw(im)
    rounded(d, (80, 65, 122, 70), WHITE if dark else BLUE, 2)
    text(d, (137, 49), name.upper(), 25, WHITE if dark else INK, True)
    text(d, (1012, 58), 'LOCAL POLICY  /  DECISION  /  EVIDENCE',
         16, SKY if dark else MUTED, False)
    return im


def opening(name: str, t: float) -> Image.Image:
    im = base(name, True)
    d = ImageDraw.Draw(im)
    rise = int((1 - smooth(t / 1.2)) * 25)
    text(d, (112, 230 + rise), 'Decisions,', 105, WHITE, True)
    text(d, (112, 350 + rise), 'made visible.', 105, WHITE, True)
    text(d, (117, 555), 'A local path from policy to inspectable evidence.', 30, SKY)
    rounded(d, (117, 718, 117 + int(350 * smooth(t / 1.5)), 724), WHITE, 3)
    return im


def crop_panel(source: Image.Image, box: tuple[int, int, int, int],
               panel: tuple[int, int, int, int], drift: float = 0) -> Image.Image:
    left, top, right, bottom = box
    w = right - left
    h = bottom - top
    # Subtle movement stays within the captured pixels.
    slide = int(58 * drift)
    left = max(0, min(source.width - w, left + slide))
    source = source.crop((left, top, left + w, bottom))
    target_w = panel[2] - panel[0]
    target_h = panel[3] - panel[1]
    scale = max(target_w / source.width, target_h / source.height)
    source = source.resize((math.ceil(source.width * scale), math.ceil(source.height * scale)),
                           Image.Resampling.LANCZOS)
    x0 = (source.width - target_w) // 2
    y0 = (source.height - target_h) // 2
    return source.crop((x0, y0, x0 + target_w, y0 + target_h))


def screen(name: str, source: Image.Image, box: tuple[int, int, int, int],
           t: float, start: float, eyebrow: str, headline: str,
           caption: str, number: int) -> Image.Image:
    im = base(name)
    d = ImageDraw.Draw(im)
    text(d, (80, 115), eyebrow, 18, BLUE, True)
    text(d, (80, 151), headline, 49, INK, True)
    text(d, (82, 224), caption, 23, MUTED)
    rounded(d, (72, 278, 1528, 825), (216, 224, 216), 21)
    rounded(d, (80, 284, 1520, 819), WHITE, 16)
    panel = (92, 296, 1508, 807)
    im.paste(crop_panel(source, box, panel, smooth((t - start) / 6)), (panel[0], panel[1]))
    d = ImageDraw.Draw(im)
    text(d, (1420, 850), f'{number:02d} / 03', 16, MUTED)
    return im


def detail(name: str, source: Image.Image, t: float) -> Image.Image:
    im = base(name)
    d = ImageDraw.Draw(im)
    text(d, (80, 115), '02  /  INSPECT', 18, BLUE, True)
    text(d, (80, 151), 'Follow the record.', 53, INK, True)
    text(d, (82, 224), 'The decision drawer surfaces the ledger check without hiding its limits.', 23, MUTED)
    rounded(d, (72, 278, 735, 825), (232, 241, 233), 21)
    text(d, (112, 329), 'RECORDED OUTCOME', 18, BLUE, True)
    text(d, (110, 381), 'read  /  permit', 43, INK, True)
    d.line((112, 478, 690, 478), fill=(190, 207, 193), width=2)
    text(d, (112, 511), 'LEDGER INTEGRITY', 18, BLUE, True)
    text(d, (110, 563), 'Passed', 43, INK, True)
    text(d, (112, 652), 'The source hash chain passed.', 22, MUTED)
    text(d, (112, 687), 'That does not prove the action was authorized.', 20, MUTED)
    rounded(d, (760, 278, 1528, 825), (216, 224, 216), 21)
    rounded(d, (768, 284, 1520, 819), WHITE, 16)
    panel = (779, 295, 1509, 807)
    im.paste(crop_panel(source, (1040, 88, 1600, 550), panel, 0),
             (panel[0], panel[1]))
    d = ImageDraw.Draw(im)
    text(d, (1420, 850), '02 / 03', 16, MUTED)
    return im


def boundary(name: str, t: float) -> Image.Image:
    im = base(name, True)
    d = ImageDraw.Draw(im)
    text(d, (104, 136), 'THE BOUNDARY', 20, SKY, True)
    text(d, (102, 184), 'A decision, with a trace.', 66, WHITE, True)
    text(d, (106, 286), 'The grant check sits where the reference tool would run.', 27, SKY)
    rounded(d, (100, 384, 1500, 536), (40, 66, 53), 18)
    rounded(d, (100, 563, 1500, 715), (40, 66, 53), 18)
    text(d, (130, 413), 'PERMIT', 17, SKY, True)
    text(d, (130, 456), 'Scoped grant    →    online verification    →    local adapter', 27, WHITE)
    text(d, (130, 592), 'EVERY DECISION', 17, SKY, True)
    text(d, (130, 635), 'Response digest    →    hash-linked ledger    →    evidence ZIP', 27, WHITE)
    progress = smooth((t - 22.9) / 1.5)
    rounded(d, (100, 765, 100 + int(950 * progress), 770), SKY, 2)
    text(d, (105, 792), 'Local prototype · other tools are not automatically gated', 20, SKY)
    return im


def closing(name: str) -> Image.Image:
    im = base(name)
    d = ImageDraw.Draw(im)
    text(d, (108, 207), name.upper(), 26, BLUE, True)
    text(d, (103, 290), 'Make the decision.', 82, INK, True)
    text(d, (103, 388), 'Keep the record.', 82, INK, True)
    d.line((108, 643, 1490, 643), fill=(205, 214, 223), width=2)
    text(d, (108, 683), 'Local single-organization prototype  /  reference adapter only', 23, MUTED)
    return im


def render(t: float, name: str, shots: list[Image.Image]) -> Image.Image:
    # Pairwise dissolves keep the edit quiet and readable.
    scenes = [
        (0, 4.5, lambda: opening(name, t)),
        (4.0, 10.7, lambda: screen(name, shots[0], (30, 275, 1570, 855), t, 4,
                                  '01  /  DECIDE', 'A policy with a visible outcome.',
                                  'One local example: permitted read, denied delete.', 1)),
        (10.2, 17.1, lambda: detail(name, shots[1], t)),
        (16.6, 23.4, lambda: screen(name, shots[2], (30, 90, 1570, 670), t, 16.6,
                                   '03  /  VERIFY', 'Check the chain. Export evidence.',
                                   'An integrity check and a downloadable evidence ZIP.', 3)),
        (22.9, 27.6, lambda: boundary(name, t)),
        (27.1, 30.6, lambda: closing(name)),
    ]
    active = [(visibility(t, start, end), painter) for start, end, painter in scenes]
    active = [(alpha, painter) for alpha, painter in active if alpha > 0.001]
    if not active:
        return opening(name, t) if t < 1 else closing(name)
    # Blend against previous scene; dissolve overlap into the next.
    result = active[0][1]()
    for alpha, painter in active[1:]:
        result = Image.blend(result, painter(), min(1, alpha))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True, help='Final project name for the film')
    ap.add_argument('--output', type=Path, default=Path('docs/showcase/demo.mp4'))
    ap.add_argument('--preview-only', action='store_true')
    ap.add_argument('screenshots', nargs=3, type=Path,
                    help='Real screenshots: policy results, decision drawer, verified export')
    args = ap.parse_args()
    shots = [Image.open(path).convert('RGB') for path in args.screenshots]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    preview = args.output.with_name(args.output.stem + '-preview.jpg')
    render(7.4, args.name, shots).save(preview, quality=88, optimize=True)
    if args.preview_only:
        print(f'Preview: {preview}')
        return
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    command = [ffmpeg, '-hide_banner', '-loglevel', 'error', '-y',
               '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '1600x900',
               '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264',
               '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
               '-movflags', '+faststart', str(args.output)]
    with subprocess.Popen(command, stdin=subprocess.PIPE) as proc:
        assert proc.stdin is not None
        for index in range(FPS * SECONDS):
            frame = render(index / FPS, args.name, shots)
            proc.stdin.write(frame.tobytes())
            if index % 100 == 0:
                print(f'Frame {index}/{FPS * SECONDS}', file=sys.stderr)
        proc.stdin.close()
        code = proc.wait()
    if code:
        raise RuntimeError(f'FFmpeg exited with status {code}')
    print(f'Video: {args.output}\nPreview: {preview}')


if __name__ == '__main__':
    main()
