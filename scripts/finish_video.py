#!/usr/bin/env python3
"""Sema finishing pass: burn Swahili/English subtitles + baked-in AI label.

Runs on the swapped output BEFORE upload so every published video carries:
  1. Optional subtitles (.srt URL) burned with FFmpeg subtitles filter.
  2. A permanent "AI-GENERATED" corner label (consent/ethics requirement).

Usage:
    python scripts/finish_video.py \
        --in output.mp4 --out final.mp4 \
        [--srt subtitles.srt] [--label "AI-GENERATED DEMO"] [--lang sw]

Exit 0 on success. Never fails the workflow on missing optionals.
"""
import argparse
import os
import shutil
import subprocess
import sys
import urllib.request


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:], flush=True)
        raise RuntimeError(f"ffmpeg failed (exit {r.returncode})")
    return r


def fetch(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": "sema/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)


def escape_drawtext(s):
    # Escape for FFmpeg drawtext filter
    return (s.replace("\\", "\\\\").replace(":", "\\:")
             .replace("'", "\\'").replace("%", "\\%"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", required=True, help="input mp4 (swapped output)")
    ap.add_argument("--out", required=True, help="finished mp4 path")
    ap.add_argument("--srt-url", default="", help="direct URL to .srt subtitles")
    ap.add_argument("--label", default="AI-GENERATED DEMO",
                    help="corner label text (empty disables)")
    ap.add_argument("--font-size", type=int, default=18)
    args = ap.parse_args()

    work = os.path.abspath("finish_work")
    os.makedirs(work, exist_ok=True)
    cur = os.path.abspath(args.inp)

    # 1. Subtitles
    srt_path = ""
    if args.srt_url.strip():
        try:
            srt_path = os.path.join(work, "subs.srt")
            fetch(args.srt_url.strip(), srt_path)
            print(f"subtitles fetched ({os.path.getsize(srt_path)} bytes)", flush=True)
        except Exception as e:
            print(f"subtitle fetch failed, continuing without: {e}", flush=True)
            srt_path = ""

    # 2. Build filter chain
    filters = []
    if srt_path:
        # Escape single quotes for the subtitles filter path
        safe = srt_path.replace("'", r"'\''")
        filters.append(
            f"subtitles='{safe}':force_style='FontSize={args.font_size},"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
            "BorderStyle=1,Outline=1,Shadow=0,MarginV=24'"
        )

    if args.label.strip():
        label = escape_drawtext(args.label.strip())
        # Bottom-right corner, semi-transparent box behind text
        filters.append(
            f"drawtext=text='{label}':fontsize={args.font_size}:"
            "fontcolor=white@0.85:borderw=1:bordercolor=black@0.6:"
            "x=w-text_w-12:y=h-text_h-12"
        )

    if not filters:
        # Nothing to do — copy through
        shutil.copyfile(cur, os.path.abspath(args.out))
        print("no finish steps requested, copied through", flush=True)
        return 0

    vf = ",".join(filters)
    out = os.path.abspath(args.out)
    run(["ffmpeg", "-y", "-i", cur, "-vf", vf,
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-c:a", "copy", out])
    print(f"finished: {out} ({os.path.getsize(out)} bytes)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
