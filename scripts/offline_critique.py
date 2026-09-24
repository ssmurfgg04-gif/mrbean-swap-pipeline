#!/usr/bin/env python3
"""4-round offline critique of a face-swap result. No API keys, runs anywhere.

Compares the original video ("before") with the swapped video ("after"):

  Round 1  Swap occurred & background preserved
           - mean absolute pixel difference inside detected face boxes (should be high)
           - mean absolute pixel difference outside face boxes (should be ~0)
  Round 2  Motion / pose preservation
           - correlation of face-box center trajectories across time (should be ~1)
  Round 3  Temporal consistency
           - flicker metric of the swapped face region vs. the original face region
             (frame-to-frame difference inside the face; the swap should not add jitter)
  Round 4  Technical quality
           - sharpness (variance of Laplacian) of the face region after vs. before
           - boundary seam check: gradient energy at the face-box border vs. inside

Verdicts: PASS / WARN / FAIL per round with simple thresholds, honest about what
offline metrics cannot judge (identity realism -> see vlm_critique.py).

Usage:
  python offline_critique.py --before src.mp4 --after out.mp4 \
      --out-md critique_report.md --out-json critique_report.json [--samples 12]
"""

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import cv2
import numpy as np

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

_DETECTOR = {"kind": None, "model": None}


def _init_detector():
    """Pick the best available face detector for this OpenCV build.

    OpenCV 4.x -> Haar cascade (bundled).
    OpenCV 5.x -> Haar was removed; use YuNet DNN (downloads a ~240 KB model once).
    """
    if _DETECTOR["kind"] is not None:
        return _DETECTOR["kind"]
    if hasattr(cv2, "CascadeClassifier") and hasattr(cv2, "data"):
        try:
            path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            _DETECTOR["model"] = cv2.CascadeClassifier(path)
            if not _DETECTOR["model"].empty():
                _DETECTOR["kind"] = "haar"
                return _DETECTOR["kind"]
        except Exception:
            pass
    try:
        import tempfile, urllib.request
        model_path = Path(tempfile.gettempdir()) / "face_detection_yunet_2023mar.onnx"
        if not model_path.exists() or model_path.stat().st_size < 10000:
            urllib.request.urlretrieve(YUNET_URL, model_path)
        _DETECTOR["model"] = cv2.FaceDetectorYN.create(str(model_path), "", (320, 320), score_threshold=0.6)
        _DETECTOR["kind"] = "yunet"
    except Exception:
        _DETECTOR["kind"] = "none"
    return _DETECTOR["kind"]


def detect_face(frame):
    """Return largest frontal face box (x, y, w, h) or None."""
    kind = _init_detector()
    if kind == "haar":
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = _DETECTOR["model"].detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
        if len(faces) == 0:
            return None
        return max(faces, key=lambda f: f[2] * f[3])
    if kind == "yunet":
        h, w = frame.shape[:2]
        try:
            _DETECTOR["model"].setInputSize((w, h))
            _, faces = _DETECTOR["model"].detect(frame)
        except Exception:
            return None
        if faces is None or len(faces) == 0:
            return None
        boxes = [(int(f[0]), int(f[1]), int(f[2]), int(f[3])) for f in faces]
        return max(boxes, key=lambda b: b[2] * b[3])
    return None


def probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def read_frames(video: str, count: int, max_w: int = 960):
    """Return [(t, frame_bgr)] at `count` evenly spaced timestamps, downscaled."""
    dur = probe_duration(video)
    margin = min(0.5, dur * 0.02)
    usable = dur - 2 * margin
    ts = [margin + usable * (i + 0.5) / count for i in range(count)]
    frames = []
    for t in ts:
        cap = cv2.VideoCapture(video)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ok, frame = cap.read()
        cap.release()
        if not ok:
            continue
        h, w = frame.shape[:2]
        if w > max_w:
            frame = cv2.resize(frame, (max_w, int(h * max_w / w)))
        frames.append((t, frame))
    return frames


def mean_abs_diff(a, b):
    if a is None or b is None or a.shape != b.shape:
        return None
    return float(np.mean(cv2.absdiff(a, b)))


def laplacian_var(gray):
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def verdict(pass_ok, warn_ok):
    if pass_ok:
        return "PASS"
    if warn_ok:
        return "WARN"
    return "FAIL"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--before", required=True)
    ap.add_argument("--after", required=True)
    ap.add_argument("--out-md", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--samples", type=int, default=12)
    args = ap.parse_args()

    before = read_frames(args.before, args.samples)
    after = read_frames(args.after, args.samples)

    report = {"rounds": {}, "meta": {"samples": len(before)}}

    # ---------------- Round 1: swap occurred & background preserved ----------
    in_face_diffs, out_face_diffs = [], []
    paired = 0
    for (tb, fb), (ta, fa) in zip(before, after):
        if fb.shape != fa.shape:
            fa = cv2.resize(fa, (fb.shape[1], fb.shape[0]))
        box = detect_face(fb)
        if box is None:
            box = detect_face(fa)
        if box is None:
            continue
        x, y, w, h = box
        pad = int(0.15 * w)
        X, Y, W, H = max(0, x - pad), max(0, y - pad), 0, 0
        W = min(fb.shape[1], x + w + pad) - X
        H = min(fb.shape[0], y + h + pad) - Y
        face_mask = np.zeros(fb.shape[:2], np.uint8)
        face_mask[Y:Y + H, X:X + W] = 255
        diff = cv2.absdiff(fb, fa)
        in_face_diffs.append(float(np.mean(diff[face_mask > 0])))
        outside = diff[face_mask == 0]
        out_face_diffs.append(float(np.mean(outside)) if outside.size else 0.0)
        paired += 1

    r1 = {"paired_frames": paired}
    if paired:
        r1["face_region_mad"] = float(np.mean(in_face_diffs))
        r1["background_mad"] = float(np.mean(out_face_diffs))
        r1["ratio"] = r1["face_region_mad"] / max(r1["background_mad"], 1e-6)
    r1["verdict"] = verdict(
        paired > 0 and r1["ratio"] > 5 and r1["background_mad"] < 6,
        paired > 0 and r1["ratio"] > 2,
    )
    report["rounds"]["round_1_swap_occurred"] = r1

    # ---------------- Round 2: motion / pose preservation --------------------
    traj_b, traj_a = [], []
    for (tb, fb), (ta, fa) in zip(before, after):
        bb, ba_ = detect_face(fb), detect_face(fa)
        if bb is None or ba_ is None:
            continue
        h = fb.shape[0]
        traj_b.append((bb[0] + bb[2] / 2, bb[1] + bb[3] / 2, bb[3] / h))
        traj_a.append((ba_[0] + ba_[2] / 2, ba_[1] + ba_[3] / 2, ba_[3] / h))
    r2 = {"tracked_frames": len(traj_b)}
    if len(traj_b) >= 3:
        bx = np.array([p[0] for p in traj_b]); ax = np.array([p[0] for p in traj_a])
        by = np.array([p[1] for p in traj_b]); ay = np.array([p[1] for p in traj_a])
        bs = np.array([p[2] for p in traj_b]); as_ = np.array([p[2] for p in traj_a])
        def corr(u, v):
            if np.std(u) < 1e-6 or np.std(v) < 1e-6:
                return 1.0
            return float(np.corrcoef(u, v)[0, 1])
        r2["x_trajectory_corr"] = corr(bx, ax)
        r2["y_trajectory_corr"] = corr(by, ay)
        r2["scale_trajectory_corr"] = corr(bs, as_)
        mean_corr = float(np.mean([r2["x_trajectory_corr"], r2["y_trajectory_corr"], r2["scale_trajectory_corr"]]))
    else:
        mean_corr = None
    r2["verdict"] = verdict(
        mean_corr is not None and mean_corr > 0.85,
        mean_corr is not None and mean_corr > 0.6,
    )
    report["rounds"]["round_2_motion_preserved"] = r2

    # ---------------- Round 3: temporal consistency (flicker) ----------------
    def region_flicker(frames, use_after_region):
        vals = []
        prev_face_img = None
        prev_gray = None
        for _, f in frames:
            box = detect_face(f)
            if box is None:
                prev_face_img = prev_gray = None
                continue
            x, y, w, h = [int(v) for v in box]
            roi = f[y:y + h, x:x + w]
            if prev_face_img is not None and prev_face_img.shape == roi.shape:
                vals.append(float(np.mean(cv2.absdiff(roi, prev_face_img))))
            prev_face_img = roi.copy()
        return float(np.mean(vals)) if vals else None

    flick_before = region_flicker(before, False)
    flick_after = region_flicker(after, True)
    r3 = {"baseline_face_flicker": flick_before, "swapped_face_flicker": flick_after}
    if flick_before is not None and flick_after is not None:
        r3["flicker_ratio"] = flick_after / max(flick_before, 1e-6)
    r3["verdict"] = verdict(
        flick_after is not None and r3.get("flicker_ratio", 99) < 1.6,
        flick_after is not None and r3.get("flicker_ratio", 99) < 2.5,
    )
    report["rounds"]["round_3_temporal_consistency"] = r3

    # ---------------- Round 4: technical quality -----------------------------
    sharp_b, sharp_a, seam = [], [], []
    for (tb, fb), (ta, fa) in zip(before, after):
        if fb.shape != fa.shape:
            fa = cv2.resize(fa, (fb.shape[1], fb.shape[0]))
        box = detect_face(fa)
        if box is None:
            continue
        x, y, w, h = [int(v) for v in box]
        roi_b = cv2.cvtColor(fb[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        roi_a = cv2.cvtColor(fa[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY)
        sharp_b.append(laplacian_var(roi_b))
        sharp_a.append(laplacian_var(roi_a))
        inner = cv2.absdiff(fb, fa)[y + h // 3: y + 2 * h // 3, x + w // 3: x + 2 * w // 3]
        edge_band = cv2.absdiff(fb, fa)[max(0, y - 8): y + h + 8, max(0, x - 8): x + w + 8]
        if inner.size and edge_band.size:
            seam.append(float(np.mean(edge_band)) - float(np.mean(inner)))
    r4 = {"frames_measured": len(sharp_a)}
    if sharp_a:
        r4["sharpness_before"] = float(np.mean(sharp_b))
        r4["sharpness_after"] = float(np.mean(sharp_a))
        r4["sharpness_ratio"] = r4["sharpness_after"] / max(r4["sharpness_before"], 1e-6)
        r4["mean_seam_excess"] = float(np.mean(seam)) if seam else None
    r4["verdict"] = verdict(
        r4.get("sharpness_ratio", 0) > 0.5 and (r4.get("mean_seam_excess") or 0) < 12,
        r4.get("sharpness_ratio", 0) > 0.25,
    )
    report["rounds"]["round_4_technical_quality"] = r4

    # ---------------- markdown ------------------------------------------------
    L = []
    L.append("## Face-Swap Critique Report (offline metrics)")
    L.append("")
    L.append(f"Sampled frames: **{len(before)}** &nbsp;|&nbsp; before: `{Path(args.before).name}` &nbsp;|&nbsp; after: `{Path(args.after).name}`")
    L.append("")
    L.append("| Round | Focus | Key numbers | Verdict |")
    L.append("|---|---|---|---|")

    def fmt(v):
        return f"{v:.3f}" if isinstance(v, float) else str(v)

    r1 = report["rounds"]["round_1_swap_occurred"]
    L.append(f"| 1 | Swap occurred, background preserved | face MAD {fmt(r1.get('face_region_mad'))}, bg MAD {fmt(r1.get('background_mad'))}, ratio {fmt(r1.get('ratio'))} | **{r1['verdict']}** |")
    r2 = report["rounds"]["round_2_motion_preserved"]
    L.append(f"| 2 | Motion / pose preserved | x-corr {fmt(r2.get('x_trajectory_corr'))}, y-corr {fmt(r2.get('y_trajectory_corr'))}, scale-corr {fmt(r2.get('scale_trajectory_corr'))} | **{r2['verdict']}** |")
    r3 = report["rounds"]["round_3_temporal_consistency"]
    L.append(f"| 3 | Temporal consistency | flicker before {fmt(r3.get('baseline_face_flicker'))}, after {fmt(r3.get('swapped_face_flicker'))}, ratio {fmt(r3.get('flicker_ratio'))} | **{r3['verdict']}** |")
    r4 = report["rounds"]["round_4_technical_quality"]
    L.append(f"| 4 | Technical quality | sharpness x{fmt(r4.get('sharpness_ratio'))}, seam excess {fmt(r4.get('mean_seam_excess'))} | **{r4['verdict']}** |")
    L.append("")
    L.append("_Offline metrics verify the mechanics of the swap (what changed, what moved, how stable, how sharp). ")
    L.append("They cannot judge whether the new identity looks truly human &mdash; that is the VLM round's job when API secrets are configured._")
    md = "\n".join(L) + "\n"

    Path(args.out_md).write_text(md, encoding="utf-8")
    Path(args.out_json).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(md)
    print(f"written: {args.out_md}, {args.out_json}")

    # non-blocking: exit 0 even on FAIL — the report is advisory data
    sys.exit(0)


if __name__ == "__main__":
    main()
