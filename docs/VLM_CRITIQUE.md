# The 4-round critique methodology

Every swap run is evaluated in **4 rounds**. Two layers exist:

1. **Offline metrics** (`scripts/offline_critique.py`) — deterministic, runs on the runner,
   no API key. Verifies the *mechanics* of the swap.
2. **VLM review** (`scripts/vlm_critique.py`, optional) — a vision-language model with a
   different lens per round. Judges *perception quality* the way a human would.

They are complementary: metrics prove what changed and how stably; the VLM judges whether
the result *looks right*.

## Round definitions

### Round 1 — Swap occurred & background preserved
- **Metric**: mean absolute difference (MAD) between before/after inside the detected face
  box vs. outside it.
- **Expectation**: inside-face MAD high (identity changed), background MAD ≈ 0 (nothing
  else touched). Ratio > 5 = clean, targeted swap.
- **Why it matters**: guards against "swapped everything" or "swapped nothing" bugs, and
  against mask bleed that damages the scene.

### Round 2 — Motion / pose preservation
- **Metric**: Pearson correlation between before/after face-box center trajectories (x, y)
  and apparent scale, sampled across the video.
- **Expectation**: correlations ≈ 1.0 — the head moves exactly where and when the original
  head moved.
- **Why it matters**: this is the "same complex movements" success criterion, quantified.

### Round 3 — Temporal consistency
- **Metric**: flicker = mean frame-to-frame difference inside the tracked face region,
  after vs. before. Ratio < 1.6× = the swap adds little visible jitter.
- **Why it matters**: per-frame independent inference can flicker; this catches it.

### Round 4 — Technical quality
- **Metrics**: Laplacian-variance sharpness of the face region after/before, plus seam
  excess (difference energy at the face-box border vs. its center).
- **Expectation**: sharpness ratio > 0.5 (face not obviously softer), seam excess < 12
  (no halo at the mask boundary).
- **Why it matters**: catches blurry pastes and visible face-box seams.

## VLM rounds (when `VLM_API_*` secrets are configured)

Any OpenAI-compatible vision endpoint works (GLM-4.5V, GPT-4o, Qwen-VL…):

| VLM round | Lens | Question |
|---|---|---|
| 1 | Identity & realism | Does the new face read as a natural human, consistent as ONE person? |
| 2 | Motion & pose fidelity | Row-by-row: same head pose and expression before/after? |
| 3 | Temporal consistency | Stable identity/tone/lighting across frames, no drift? |
| 4 | Technical quality | Seams, color mismatch, resolution mismatch, mask-edge cuts? |

Each round returns `VERDICT: PASS | WARN | FAIL` and a short justification; the overall
verdict is the worst round. Reports land in the run Summary and in artifacts.

## Interpreting combined results

| Offline | VLM | Meaning |
|---|---|---|
| PASS | PASS | Ship it. |
| PASS | WARN | Mechanically clean; try higher `pixel_boost` / different model. |
| FAIL (R2) | — | Wrong face tracked — fix selector order/position. |
| FAIL (R3) | — | Flicker — lower pixel boost, enable occlusion mask. |
| PASS | FAIL | Realism problem — try `hyperswap_1a_256` + GFPGAN, better reference photo. |

## Limitations (honesty section)

- Offline metrics use a frontal Haar detector; strong profile shots reduce sample counts.
- VLM verdicts depend on the chosen model's calibration; keep temperature 0.2 (default).
- Neither layer judges *ethical* appropriateness — see the README ethics section.
