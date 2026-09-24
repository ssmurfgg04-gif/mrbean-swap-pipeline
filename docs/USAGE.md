# Usage — step by step

Everything runs on GitHub's servers. You never need Python, ffmpeg, or a GPU locally.

## 0. One-time setup

1. **Use this repo** — push it / fork it under your account (it already lives at
   `https://github.com/<owner>/mrbean-swap-pipeline`).
2. Make sure **Actions are enabled**: repo → *Settings → Actions → General* →
   "Allow all actions and reusable workflows" is fine.
3. (Optional, for the VLM critique rounds) repo → *Settings → Secrets and variables → Actions*
   → add three secrets:
   - `VLM_API_BASE` — e.g. `https://api.z.ai/api/paas/v4`
   - `VLM_API_KEY`  — your key
   - `VLM_MODEL`    — e.g. `glm-4.5v`
   Without these, the offline critique still runs; the VLM rounds are simply skipped.

## 1. Host your media where the runner can fetch it

Both workflow inputs are **direct URLs**. Easy options:

- **GitHub release** (recommended): repo → *Releases → Draft a new release* → attach your
  `video.mp4` and `new_face.jpg` → publish → copy the asset URLs.
- Any public file host / S3 / CDN with direct links.
- The bundled public-domain sample: `assets/samples/sample_face_A.jpg` is reachable at
  `https://raw.githubusercontent.com/<owner>/mrbean-swap-pipeline/main/assets/samples/sample_face_A.jpg`.

Requirements for the reference face: one person, frontal, well-lit, no sunglasses/masks,
face occupies a decent part of the image (≥ 300 px).

## 2. Run the swap

### Workflow 02 — Simple (recommended default)

repo → **Actions** → **02 · Simple Swap (CPU, single job)** → **Run workflow** →

| Field | What to put |
|---|---|
| `target_video_url` | URL of your video |
| `source_face_url` | URL of the NEW face image |
| `face_selector_order` | `left-right` (most natural reading order) |
| `reference_face_position` | `0` = primary subject, `1` = **second subject**, `2` = third… |
| `swapper_model` | `inswapper_128` (fast) or `hyperswap_1a_256` (sharper) |
| `pixel_boost` | `256x256` balanced, `512x512` detailed, `1024x1024` max |
| `use_face_enhancer` | `true` |

Click **Run workflow**. Progress: Actions → click the running job → watch logs
(model download happens once, then it's cached).

### Workflow 03 — Parallel (videos longer than ~2 min)

Same inputs, plus `chunk_seconds` (default 45) and `max_chunks` (default 8 —
that's 8 parallel runners). The video is split, all chunks are swapped in
parallel, then merged losslessly.

### Workflow 01 — Smoke test

Just click Run with defaults. Confirms install → model download → detection →
swap → encode all work on a fresh runner, in ~5–10 minutes.

## 3. Get your result

When the run finishes (green check):

1. Open the run → scroll to **Artifacts**.
2. Download **`swap-output`** (or `swap-output-parallel`):
   - `output.mp4` — the swapped video (audio preserved)
   - `contact_sheet.png` — before/after frame grid
   - `critique_report.md` / `.json` — the 4-round offline critique
3. The same report is rendered in the run's **Summary** tab.
4. Artifacts are kept 90 days.

## 4. Reading the critique report

| Round | Meaning | PASS looks like |
|---|---|---|
| 1 Swap occurred | Face region changed, background untouched | face MAD ≫ background MAD (ratio > 5), bg MAD < 6 |
| 2 Motion preserved | Face-center trajectory correlates before/after | correlations > 0.85 |
| 3 Temporal consistency | Swap didn't add flicker | flicker ratio < 1.6× baseline |
| 4 Technical quality | Swapped face sharp, no seam halo | sharpness ratio > 0.5, seam excess < 12 |

WARN = acceptable but tunable. FAIL = see troubleshooting below.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| "No face detected" in logs | Better reference photo (larger/frontal); or lower `--face-detector-score` via `extra_args` |
| Wrong face got swapped | Try `face_selector_order`: `large-small` (primary subject), `small-large`, `right-left`; adjust `reference_face_position` |
| Swap only on part of frames (subject turns away) | Frontal-only limitation of the detector; add `--face-detector-angles 0 -1` via `extra_args` to also scan flipped frames (slower) |
| 55-minute job timeout | Use workflow 03, or `--trim-frame-start/end` via `extra_args`, lower `pixel_boost` |
| Whole run 429s on your URLs | Re-host media on a GitHub release; URLs must be direct-download |
| Output washed out / soft | Raise `output_video_quality` to 90+, use `hyperswap_1a_256` + `512x512` boost |
| Flicker between frames | Lower `pixel_boost`; `face_mask_types` = `box occlusion`; try different `swapper_model` |
| Chunk concat artifacts (workflow 03) | Set `chunk_seconds` higher (fewer boundaries) or use workflow 02 |

## 6. Making a demo clip with zero external media

```bash
# on any machine with ffmpeg (or locally in a runner):
./scripts/make_demo_clip.sh assets/samples/sample_face_A.jpg demo_target.mp4
```

Then point workflow 02 at that clip (host it first) with
`source_face_url` = raw URL of `sample_face_B.jpg`.
