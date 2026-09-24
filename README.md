# Sema — say it in your video

**Free video localization for Kenyan creators: swap a face, burn Swahili subtitles, stamp an AI label. No GPU. No local compute. No cost.**

> *Sema* means **"say / speak"** in Swahili. Pick any video, put your language and your face in it — free, from a browser.

---

## The problem

Kenya's creator economy runs on video — skits, explainers, ₿iz plugs — but professional localization is priced for someone else:

- A 60-second subtitled edit costs **more than most creators earn** from the video itself.
- 84% of the global population has never used AI, and almost no video tooling speaks Swahili or Sheng first.
- Face-swap and dubbing tools need gaming GPUs nobody here owns.

So local stories stay local-language-only, and global content stays English-only.

## The proposed solution

Sema is a **consent-gated, CPU-only video pipeline** that runs entirely on free cloud runners:

1. **Face-swap** any subject with any consented face (FaceFusion, ONNX CPU — motion preserved by construction).
2. **Burn subtitles** — upload an `.srt` (Swahili, English, Sheng) and they're baked into the MP4.
3. **Stamp an AI label** — every output carries a permanent `AI-GENERATED` corner mark. No exceptions.
4. **Quality proof** — a 4-round offline critique (swap check, motion preservation, flicker, sharpness) ships with every run, plus an optional VLM review.

Nothing runs on your machine. Trigger from the Actions tab (2 fields), collect the MP4 from Artifacts. A hosted [Gradio demo](app.py) does the lightweight finishing (subtitles + label) instantly, and generates the exact swap-job inputs for you.

## Current progress

- [x] CPU face-swap pipeline (3 workflows: smoke test, single job, parallel matrix)
- [x] 4-round offline critique + optional VLM review with merged reports
- [x] Contact-sheet before/after reports on every run
- [x] **NEW — subtitle burn-in** (`scripts/finish_video.py`, SRT → styled MP4)
- [x] **NEW — mandatory AI watermark** (baked-in corner label on all outputs)
- [x] **NEW — consent gate** (workflows refuse to run unless confirmed)
- [x] **NEW — hosted Gradio demo** (`app.py`: finish-a-video tab + swap planner)
- [x] Ethics & legal section, troubleshooting, route comparison docs
- [ ] Live demo Space deployment (needs HF account link)
- [ ] Swahili TTS voiceover track (Fish Audio integration)
- [ ] Lip-sync pass (LatentSync, CPU-feasible at 256px — in testing)

## Quickstart (2 minutes, free)

1. Open **Actions → 02 · Simple Swap → Run workflow**.
2. Fill in:
   - `target_video_url` — direct link to the video (mp4/mov/webm)
   - `source_face_url` — direct link to the **consented** new face (jpg/png)
   - Tick `consent_confirm` (required — the run refuses without it)
   - Optional: `subtitles_url` (direct `.srt` link), `watermark_text`
3. Click **Run workflow**. Download `final.mp4` from **Artifacts**.

No GPU. No install. Public repos get free unlimited Actions minutes.

## Repository layout

```
.github/workflows/
  01-smoke-test.yml        # sanity check on official sample media
  02-swap-simple.yml       # one-job swap + subtitles + AI label
  03-swap-parallel.yml     # chunked matrix swap + subtitles + AI label
scripts/
  finish_video.py          # NEW: subtitle burn-in + corner AI label
  make_contact_sheet.py    # before/after frame grid for reports
  offline_critique.py      # 4-round metric critique (no API needed)
  vlm_critique.py          # 4-round VLM critique (optional)
  make_demo_clip.sh        # Ken Burns demo clip from a still
app.py                     # NEW: hosted Gradio demo (finish + plan tabs)
requirements-demo.txt      # NEW: demo deps (gradio only)
docs/
  ROUTE.md                 # why FaceFusion-on-Actions beat the alternatives
  USAGE.md                 # step-by-step usage + troubleshooting
  VLM_CRITIQUE.md          # critique methodology & score interpretation
assets/samples/            # public-domain portrait for smoke tests
```

## Cost

Public repos get **free unlimited** GitHub Actions minutes on standard runners. A full swap typically takes 10–55 min of free compute. The Gradio demo runs on Hugging Face's free tier.

## Ethics & legal — read before using

This pipeline produces photorealistic media of a person who did not say or do what the output shows.

- **Consent is enforced, not suggested**: workflows abort unless `consent_confirm` is ticked, and every output carries a baked-in AI label.
- **Label it**: anything you publish must be marked synthetic.
- **No harm**: no political disinformation, no sexual content, no impersonation for fraud.
- FaceFusion's NSFW analyser stays enabled and aborts on flagged input.
- You are the operator. This repo ships the same capability as the upstream open-source tools and inherits their responsibility model.

## Team

Solo-built for Hack for Humanity: Nairobi (AI Collective) — open to collaborators, technical and non-technical. Reach out via GitHub issues.

## Project story

Built in Nairobi, for Nairobi's creators — because the 84% deserve tools in their language, on hardware they already own (a phone and a browser). Sema started as a face-swap experiment and grew into a localization studio the week of the hackathon: subtitles for Sheng-speaking audiences, consent gates because synthetic media without them is a weapon, and a demo anyone can run without installing anything.

## Credits & licenses

- [FaceFusion](https://github.com/facefusion/facefusion) (its own license) — detection/swap/encode engine.
- Model weights (INSightFace INSwapper, HyperSwap, GFPGAN, YOLO-face) carry their own licenses; several are **non-commercial**.
- Everything else in this repo: MIT — see [LICENSE](LICENSE).
