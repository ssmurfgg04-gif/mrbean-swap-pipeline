#!/usr/bin/env python3
"""4-round VLM critique of a face-swap result using any OpenAI-compatible
vision-chat endpoint (e.g. GLM-4.5V, GPT-4o, Qwen-VL).

Configuration (env vars):
  VLM_API_BASE   e.g. https://api.openai.com/v1  or  https://api.z.ai/api/paas/v4
  VLM_API_KEY    the API key
  VLM_MODEL      e.g. glm-4.5v / gpt-4o / qwen2.5-vl-72b-instruct
  VLM_SAMPLES    frames sampled per side (default 8)

Rounds (a different lens each round):
  1  Identity & realism      — does the swapped face read as a natural human face
                               matching the reference person?
  2  Motion & pose fidelity  — do BEFORE/AFTER pairs show the same head pose and
                               expression trajectory (i.e. same complex movements)?
  3  Temporal consistency    — across the AFTER samples, is the identity stable,
                               without flicker or identity drift?
  4  Technical quality       — blending, color/lighting match, boundary seams,
                               resolution mismatch artifacts.

Usage:
  python vlm_critique.py --before src.mp4 --after out.mp4 --out-md vlm_report.md
                          [--reference source.jpg]
"""

import argparse
import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import requests

API_BASE = os.environ.get("VLM_API_BASE", "")
API_KEY = os.environ.get("VLM_API_KEY", "")
MODEL = os.environ.get("VLM_MODEL", "glm-4.5v")
SAMPLES = int(os.environ.get("VLM_SAMPLES", "8"))

ROUNDS = [
    {
        "title": "Round 1 — Identity & realism",
        "prompt": (
            "You are a forensic VLM reviewer. Image 1 is a contact sheet BEFORE a face swap, "
            "image 2 is the AFTER sheet. Look closely at the faces in the AFTER sheet.\n"
            "1) Does the AFTER face read as a natural, photorealistic human face (not a mask, "
            "not pasted, no uncanny artifacts)?\n"
            "2) Is the identity consistent with a single person across the sampled frames?\n"
            "Answer in <=120 words, then output exactly one line: VERDICT: PASS or WARN or FAIL."
        ),
    },
    {
        "title": "Round 2 — Motion & pose fidelity",
        "prompt": (
            "You are reviewing a face swap where the whole point is that the person must perform "
            "exactly the same movements as in the original. Each row of the two contact sheets "
            "shows the SAME timestamp before and after.\n"
            "1) Compare rows one by one: is the head pose (yaw/pitch/roll) and facial expression "
            "the same before and after?\n"
            "2) Is any motion energy lost (e.g. blurred mid-motion faces becoming static-looking)?\n"
            "Answer in <=120 words, then output exactly one line: VERDICT: PASS or WARN or FAIL."
        ),
    },
    {
        "title": "Round 3 — Temporal consistency",
        "prompt": (
            "Image 1 shows frames sampled across the ORIGINAL video, image 2 the same timestamps "
            "after the face swap. Evaluate temporal stability of the swapped face:\n"
            "1) Does the identity, skin tone and lighting of the new face stay constant across frames?\n"
            "2) Any signs of flicker, popping, or identity drift between frames?\n"
            "Answer in <=120 words, then output exactly one line: VERDICT: PASS or WARN or FAIL."
        ),
    },
    {
        "title": "Round 4 — Technical quality",
        "prompt": (
            "You are a compositing QA reviewer. In the AFTER sheet (image 2), inspect each swapped "
            "face for: face-box boundary seams, color/brightness mismatch with the surrounding skin, "
            "resolution mismatch (face sharper or softer than the rest of the frame), and mask edges "
            "cutting through hair or glasses.\n"
            "Answer in <=120 words, then output exactly one line: VERDICT: PASS or WARN or FAIL."
        ),
    },
]


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def extract_frames(video: str, count: int, width: int, tmpdir: str, tag: str):
    dur = probe_duration(video)
    margin = min(0.5, dur * 0.02)
    usable = dur - 2 * margin
    ts = [margin + usable * (i + 0.5) / count for i in range(count)]
    paths = []
    for i, t in enumerate(ts):
        p = str(Path(tmpdir) / f"{tag}_{i:03d}.jpg")
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-ss", f"{t:.3f}", "-i", video,
             "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", p],
            check=True, capture_output=True,
        )
        paths.append(p)
    return paths


def grid(paths: list, cols: int, out: str, width: int, label: str):
    from PIL import Image, ImageDraw, ImageFont
    imgs = [Image.open(p) for p in paths]
    h = imgs[0].height
    rows = (len(imgs) + cols - 1) // cols
    sheet = Image.new("RGB", (width * cols + 8 * (cols + 1), (h + 34) * rows + 8), (18, 18, 24))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except Exception:
        font = ImageFont.load_default()
    for i, im in enumerate(imgs):
        r, c = divmod(i, cols)
        x = 8 + c * (width + 8)
        y = 8 + r * (h + 34)
        sheet.paste(im, (x, y))
        d.text((x + 4, y + h + 5), f"{label} #{i + 1}", fill=(200, 200, 210), font=font)
    sheet.save(out)
    return out


def b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def chat(images: list, prompt: str) -> str:
    url = API_BASE.rstrip("/") + "/chat/completions"
    content = [{"type": "text", "text": prompt}]
    for p in images:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64(p)}"},
        })
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"model": MODEL, "messages": [{"role": "user", "content": content}], "temperature": 0.2},
        timeout=180,
    )
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--reference", default=None, help="optional reference face image")
    args = ap.parse_args()

    if not (API_BASE and API_KEY):
        print("VLM_API_BASE / VLM_API_KEY not set; skipping VLM critique.", file=sys.stderr)
        sys.exit(0)

    tmp = tempfile.mkdtemp(prefix="vlm_")
    before_frames = extract_frames(args.before, SAMPLES, 512, tmp, "b")
    after_frames = extract_frames(args.after, SAMPLES, 512, tmp, "a")

    sheet_b = grid(before_frames, 4, str(Path(tmp) / "sheet_before.jpg"), 512, "BEFORE")
    sheet_a = grid(after_frames, 4, str(Path(tmp) / "sheet_after.jpg"), 512, "AFTER")

    L = ["## Face-Swap Critique Report (VLM, 4 rounds)", ""]
    L.append(f"Model: `{MODEL}` &nbsp;|&nbsp; samples per side: {SAMPLES}")
    L.append("")
    verdicts = []
    for rnd in ROUNDS:
        imgs = [sheet_b, sheet_a]
        if args.reference:
            imgs = [args.reference] + imgs
        try:
            answer = chat(imgs, rnd["prompt"])
        except Exception as e:  # noqa: BLE001
            answer = f"(VLM call failed: {e})"
        v = "N/A"
        for line in answer.splitlines()[::-1]:
            if "VERDICT:" in line.upper():
                v = line.split(":")[-1].strip().upper()[:4]
                break
        verdicts.append(v)
        L.append(f"### {rnd['title']}  —  **{v}**")
        L.append("")
        L.append(answer)
        L.append("")
    overall = "FAIL" if "FAIL" in verdicts else ("WARN" if "WARN" in verdicts else "PASS")
    L.append(f"**Overall VLM verdict: {overall}** (rounds: {', '.join(verdicts)})")
    md = "\n".join(L) + "\n"

    Path(args.out_md).write_text(md, encoding="utf-8")
    Path(args.out_md + ".json").write_text(
        json.dumps({"rounds": verdicts, "overall": overall}, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
