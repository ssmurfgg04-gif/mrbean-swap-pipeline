# mrbean-swap-pipeline

**Replace any subject in a video with another face — 100% CPU, 100% on GitHub's servers, zero local hardware.**

> Born from a mission: *"take a video of Jackie Chan and replace Jackie Chan with Mr Bean
> pulling off the same complex movements."* Motion preservation comes for free with per-frame
> aligned face swapping — the body, the moves, the timing all stay identical; only the identity
> inside the face region changes. This repo is the reusable, no-GPU pipeline that came out of it.

---

## Why this route (TL;DR)

| Requirement | Solution |
|---|---|
| No GPU available | FaceFusion with `onnxruntime` **CPU** execution provider (INSwapper / HyperSwap ONNX models) |
| No local compute at all | Everything runs on **GitHub Actions `ubuntu-latest` runners** (4 vCPU / 16 GB RAM) |
| Keep the *same complex movements* | Per-frame face swap is **motion-preserving by construction**: pose, expression and timing are inherited from the source video every frame |
| Precisely target the *second* subject | `--face-selector-order left-right --reference-face-position 1` (0-based positional selection) |
| Quality assessment | 4-round critique: offline metrics on the runner + optional VLM review |
| Reusable forever | Every workflow takes plain URLs as inputs — no code edits needed |

Full technical route comparison: [`docs/ROUTE.md`](docs/ROUTE.md).

## The three workflows

| Workflow | What it does | When to use | Runtime |
|---|---|---|---|
| [`01-smoke-test.yml`](.github/workflows/01-smoke-test.yml) | Installs FaceFusion, downloads models, runs a 25-frame real swap on official sample media | First run / sanity check / warm the model cache | ~5–10 min |
| [`02-swap-simple.yml`](.github/workflows/02-swap-simple.yml) | Single-job swap of any video (≤ ~2 min long recommended) | Most videos, most precise | 10–55 min |
| [`03-swap-parallel.yml`](.github/workflows/03-swap-parallel.yml) | Splits the video into chunks, swaps all chunks **in parallel** (matrix), merges back | Longer videos when you're in a hurry | ~10–25 min regardless of length |

All three are triggered manually from the **Actions tab → select workflow → Run workflow**,
fill 2 input fields (target video URL + source face URL), wait, then download the result from
the run's **Artifacts** section. Nothing ever touches your machine.

## Quickstart (2 minutes)

1. Fork or use this repo as-is.
2. Open the **Actions** tab → **02 · Simple Swap (CPU, single job)** → **Run workflow**.
3. Fill in:
   - `target_video_url` — direct link to the video (mp4/mov/webm).
     Default is an official FaceFusion test clip so you can just hit Run.
   - `source_face_url` — direct link to a photo of the **new** face (e.g. a Mr Bean still).
   - `face_selector_order` = `left-right` and `reference_face_position` = `1`
     → replaces the **second subject from the left** (the Jackie Chan position).
     Use `0` for the primary/largest subject, `all` to replace everyone.
4. Click **Run workflow**. When it finishes, download `output-video` from **Artifacts**.

Detailed walkthrough incl. screenshots-in-words and troubleshooting: [`docs/USAGE.md`](docs/USAGE.md).

## The Jackie Chan → Mr Bean recipe

```
target_video_url:      (your video: direct URL to the mp4)
source_face_url:       (a clear, frontal, well-lit Mr Bean reference photo URL)
face_selector_order:   left-right        # stable spatial ordering
reference_face_position: 1               # 0-based → "second subject"
reference_frame_number:  0
swapper_model:         hyperswap_1a_256  # best CPU quality; inswapper_128 = fastest
pixel_boost:           512x512           # 256x256 = faster, 1024x1024 = max detail
```

If "second subject" means something else in your video (e.g. second from the *right*,
or the smaller of two), change `face_selector_order` accordingly: `right-left`,
`top-bottom`, `small-large`, `large-small`, `best`, or `all`.

## Quality knobs (CPU-cost vs. quality)

| Knob | Fast / low | Slow / high |
|---|---|---|
| `swapper_model` | `inswapper_128` (~0.6 s/frame) | `hyperswap_1a_256` (~1.5 s/frame, sharper) |
| `pixel_boost` | `128x128` / `256x256` | `512x512` / `1024x1024` |
| `use_face_enhancer` | `false` | `true` (GFPGAN 1.4 post-pass) |
| `face_mask_types` | `box` | `box occlusion` (keeps hair/hands over face) |

Throughput measured on `ubuntu-latest` (4 vCPU): **inswapper_128 @ 540p ≈ 2 fps**,
so a 60 s clip finishes in ~8 min inside one job. The parallel workflow chunks long
videos so wall-clock time stays bounded.

## Output quality: the 4-round critique

Every swap workflow automatically appends a **critique report** to the run summary:

- **Round 1 — Swap occurred & background preserved** (face region changed, background untouched)
- **Round 2 — Motion / pose preservation** (face-center trajectory correlation before vs. after)
- **Round 3 — Temporal consistency** (flicker of the swapped region vs. baseline)
- **Round 4 — Technical quality** (sharpness of the swapped face, boundary seams)

These are computed offline by [`scripts/offline_critique.py`](scripts/offline_critique.py) on the runner.
If you add repo secrets (`VLM_API_BASE`, `VLM_API_KEY`, `VLM_MODEL` — any OpenAI-compatible
vision endpoint, e.g. GLM-4.5V), [`scripts/vlm_critique.py`](scripts/vlm_critique.py) additionally
runs a 4-round **VLM** review with a different lens per round and merges both into the report.
Methodology: [`docs/VLM_CRITIQUE.md`](docs/VLM_CRITIQUE.md).

## Repository layout

```
.github/workflows/
  01-smoke-test.yml        # end-to-end sanity check on official sample media
  02-swap-simple.yml       # one-job swap, full precision
  03-swap-parallel.yml     # chunked matrix swap for long videos
scripts/
  make_contact_sheet.py    # before/after frame grid used in reports
  offline_critique.py      # 4-round metric-based critique (no API needed)
  vlm_critique.py          # 4-round VLM critique (optional, any OpenAI-compatible API)
  make_demo_clip.sh        # build a Ken Burns demo clip from a still portrait
docs/
  ROUTE.md                 # why FaceFusion-on-Actions beat the alternatives
  USAGE.md                 # step-by-step usage + troubleshooting
  VLM_CRITIQUE.md          # critique methodology & score interpretation
assets/samples/            # bundled public-domain portrait (Lincoln O-77, Library of Congress)
```

## Cost

Public repos get **free unlimited** GitHub Actions minutes on standard runners.
This repo is designed for public use. On private repos, a full swap typically burns
10–60 standard minutes per run.

## Ethics & legal — read before using

This pipeline produces photorealistic media of a person who did not say or do what the
output shows. That has real-world consequences.

- **Consent**: only swap faces of people who agreed to it. Swapping in a celebrity
  (Mr Bean / Rowan Atkinson) or *out* a celebrity (Jackie Chan) for anything published
  is very likely unlawful in your jurisdiction and against several platforms' ToS.
- **Label it**: if you publish a test result, label it clearly as synthetic (e.g. "deepfake demo").
- **No harm**: no political disinformation, no sexual content, no impersonation for fraud.
- FaceFusion's built-in NSFW content analyser remains enabled by default and will abort
  on detected NSFW input.
- You are the operator. This repo ships the same capability as the upstream open-source
  tools (FaceFusion, INSwapper) and inherits their responsibility model.

## Troubleshooting (short)

| Symptom | Fix |
|---|---|
| `No face detected in source` | Use a larger, frontal, unobstructed reference photo (≥ 300 px face) |
| Wrong face swapped | Nudge `reference_face_position`, or switch `face_selector_order` |
| Job killed at 55 min | Video too long for one job → use workflow 03, or lower `pixel_boost` |
| Output flickers | Lower `pixel_boost`, add `occlusion` to `face_mask_types`, try `hyperswap_1a_256` |
| 429 / download errors on input URLs | Host your media somewhere stable (e.g. a GitHub release) — URLs must be directly fetchable |

## Credits & licenses

- [FaceFusion](https://github.com/facefusion/facefusion) (open source, its own license applies) — the engine doing detection/swap/encode.
- Model weights (INSwapper by InsightFace, HyperSwap, GFPGAN, YOLO-face, 2DFAN, XSeg, BiSeNet) carry their respective licenses; several are **non-commercial**.
- `assets/samples/sample_face_A.jpg`: Abraham Lincoln, O-77 matte collodion print — public domain (Library of Congress via Wikimedia Commons).
- Everything else in this repo: MIT — see [LICENSE](LICENSE).
