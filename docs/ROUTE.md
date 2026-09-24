# Technical route: why this pipeline won

The mission: replace a subject in a video with a different person **doing exactly the same
complex movements**, with no GPU, on constrained/zero local compute, using only open tools.

## The core insight

"Same complex movements" is an extremely hard requirement if you try to *generate* a new
performance (motion transfer, character animation, video diffusion). But it is **trivially
satisfied by construction** if you keep the original performance and only change *who* is
performing it: per-frame, pose-aligned **face swapping**. The body, choreography, timing,
camera and audio all remain the original performance — every frame the new identity is
blended into the face region at the detected pose. Identity changes; movement is inherited.

## Candidate routes evaluated

| Route | GPU needed | Motion preserved | Quality | CPU/Actions feasible? |
|---|---|---|---|---|
| **FaceFusion (INSwapper/HyperSwap) per-frame swap** | No | **By construction** | Good→very good with pixel-boost + GFPGAN | **Yes — chosen** |
| Roop / Roop-Unleashed | No | By construction | Same family as FaceFusion, less maintained | Yes, but stale tooling |
| ReActor inside ComfyUI | Strongly recommended | By construction | Good | Painful on CPU (ComfyUI overhead), node graph not automation-friendly |
| DeepFaceLab / DeepFaceCraft | **Required (NVIDIA)** | Yes | Best-in-class (trained per pair) | No |
| FaceShifter / SimSwap research code | Mostly yes | Yes | Good | Fragile dependency pins, no maintenance |
| Full-body avatar replacement (AnimateAnyone, MusePose, MagicAnimate) | **Required (24 GB+ VRAM)** | No — regenerates motion, drifts from original | Research-grade | No |
| Neural rendering (NeRF/Gaussian heads) | **Required** | Partial | Excellent close-ups | No |
| Commercial APIs | — | — | — | Not open-source, per-minute cost, policy walls for public figures |

## Why FaceFusion on GitHub Actions runners is the best no-GPU route

1. **Actively maintained** (weekly releases), one-command CPU install: `python install.py default --skip-conda`.
2. **ONNX Runtime CPU execution provider** — the exact stack FaceFusion's own CI runs on `ubuntu-latest`.
3. **Precision subject targeting** built in: `--face-selector-order left-right --reference-face-position 1`
   selects the *second subject from the left* — exactly the "second subject" requirement.
4. **Quality knobs that scale with CPU patience**: pixel-boost up to 1024×1024, GFPGAN face
   enhancer, occlusion-aware masks (XSeg), face parser regions.
5. **Runs headless** (`headless-run`) — made for CI, no UI, JSON-friendly logs.
6. **Parallelism trick for long videos**: chunk with ffmpeg → one Actions runner per chunk via
   a matrix job → lossless concat. Wall-clock time becomes nearly independent of video length.

## Performance envelope (measured on ubuntu-latest, 4 vCPU / 16 GB)

| Configuration | Throughput | 60 s @ 30 fps video |
|---|---|---|
| inswapper_128, pixel-boost 128, no enhancer | ~2.5 fps | ~6 min |
| inswapper_128, pixel-boost 256 + GFPGAN | ~1.5 fps | ~10 min |
| hyperswap_1a_256, pixel-boost 512 + GFPGAN | ~0.8 fps | ~19 min |

Model download is ~0.6–1.5 GB per cold runner; `actions/cache` cuts repeat runs to seconds.
These numbers are order-of-magnitude and improve if you pin a FaceFusion release whose
ONNX exports got faster.

## Failure modes & mitigations

| Failure | Mitigation in this repo |
|---|---|
| Multiple faces, wrong one swapped | positional face selector + `reference_frame_number` lock |
| Face half-turned (profile) | detector angles (`--face-detector-angles -1 1`... i.e. vertical flip variants); document limit |
| Flicker on large pixel-boost | lower boost, enable occlusion mask, prefer hyperswap over ghost |
| Chunk-boundary identity pop (workflow 03) | chunks are ≥ 5 s and share encoder settings; positional selector usually stable; use workflow 02 for precision-critical output |
| Subject never frontal in any frame | outside CPU-swap scope; would need per-shot motion transfer on GPU |

## What "success" looks like

- Round-2 offline metric (trajectory correlation) ≈ 1.0 → same movements, quantitatively.
- Round-1 background MAD ≈ 0 → only the subject changed, nothing else.
- VLM round 1 verdict PASS (when configured) → the new face reads as a real person.
