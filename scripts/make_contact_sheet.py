#!/usr/bin/env python3
"""Build a labeled before/after contact sheet from two videos.

Extracts N frames at evenly spaced timestamps from both videos and composes
a 2-column grid: left = before (source), right = after (swapped).

Usage:
  python make_contact_sheet.py --before src.mp4 --after out.mp4 \
      --out contact_sheet.png --frames 6 [--width 480]
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_frames(video: str, timestamps, width: int, tmpdir: str, tag: str):
    paths = []
    for i, ts in enumerate(timestamps):
        out_path = str(Path(tmpdir) / f"{tag}_{i:03d}.png")
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{ts:.3f}", "-i", video,
            "-frames:v", "1",
            "-vf", f"scale={width}:-2",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        paths.append(out_path)
    return paths


def load_font(size: int):
    for name in ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "Arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--frames", type=int, default=6)
    ap.add_argument("--width", type=int, default=480)
    args = ap.parse_args()

    d_before = probe_duration(args.before)
    try:
        d_after = probe_duration(args.after)
    except Exception:
        d_after = d_before
    span = min(d_before, d_after)
    if span <= 0:
        print("Video duration is zero; nothing to do.", file=sys.stderr)
        sys.exit(1)

    n = max(1, args.frames)
    # avoid the very first/last frames (often black or detection misses)
    margin = min(0.5, span * 0.02)
    usable = span - 2 * margin
    timestamps = [margin + usable * (i + 0.5) / n for i in range(n)]

    with tempfile.TemporaryDirectory() as tmpdir:
        before_paths = extract_frames(args.before, timestamps, args.width, tmpdir, "before")
        after_paths = extract_frames(args.after, timestamps, args.width, tmpdir, "after")

        first = Image.open(before_paths[0])
        row_h = first.height
        label_h = 40
        pad = 8

        sheet = Image.new(
            "RGB",
            (args.width * 2 + pad * 3, (row_h + label_h) * n + pad * (n + 1)),
            (18, 18, 24),
        )
        draw = ImageDraw.Draw(sheet)
        font = load_font(22)

        for i in range(n):
            y = pad + i * (row_h + label_h)
            bx = pad
            ax = pad * 2 + args.width
            sheet.paste(Image.open(before_paths[i]), (bx, y))
            sheet.paste(Image.open(after_paths[i]), (ax, y))
            draw.text((bx + 6, y + row_h + 8), f"BEFORE  t={timestamps[i]:.2f}s", fill=(180, 180, 190), font=font)
            draw.text((ax + 6, y + row_h + 8), f"AFTER   t={timestamps[i]:.2f}s", fill=(120, 220, 160), font=font)

        sheet.save(args.out)
        print(f"contact sheet written: {args.out} ({sheet.width}x{sheet.height})")


if __name__ == "__main__":
    main()
