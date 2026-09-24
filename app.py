"""Sema demo — hosted Gradio UI (Hugging Face Spaces, free tier).

What this demo does ON the Space (lightweight, CPU-fine):
  1. Subtitle burn-in: upload a video + .srt, get subtitled MP4 back.
  2. AI-label stamping: bakes a permanent "AI-GENERATED" corner label.
  3. Job planner: fill the swap form, get the exact GitHub Actions
     inputs JSON + one-click link to launch the heavy swap there.

The heavy face-swap itself runs on GitHub Actions (free runners),
not here — this Space stays fast for everyone.
"""

import json
import os
import shutil
import subprocess
import tempfile
import urllib.parse

import gradio as gr

WORK = os.path.join(tempfile.gettempdir(), "sema_demo")
os.makedirs(WORK, exist_ok=True)

REPO_ACTIONS = "https://github.com/ssmurfgg04-gif/sema/actions/workflows/02-swap-simple.yml"


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-1500:] or "ffmpeg failed")
    return r


def finish_demo(video_path, srt_file, label):
    """Burn subtitles + AI label into an uploaded video."""
    if not video_path:
        raise gr.Error("Upload a video first.")
    out = os.path.join(WORK, "finished.mp4")
    cmd = ["python", "scripts/finish_video.py",
           "--inp", video_path, "--out", out]
    if srt_file:
        # Gradio gives a local path; finish_video.py wants a URL —
        # copy locally and pass via file:// is NOT supported, so we
        # inline: temporarily serve is overkill; instead reuse the
        # filter directly here for local files.
        pass
    # Local path: build the filter inline (same logic as finish_video.py)
    filters = []
    if srt_file:
        safe = srt_file.replace("'", r"'\''")
        filters.append(
            f"subtitles='{safe}':force_style='FontSize=18,"
            "PrimaryColour=&H00FFFFFF,OutlineColour=&H80000000,"
            "BorderStyle=1,Outline=1,Shadow=0,MarginV=24'"
        )
    if label and label.strip():
        esc = (label.replace("\\", "\\\\").replace(":", "\\:")
                     .replace("'", "\\'").replace("%", "\\%"))
        filters.append(
            f"drawtext=text='{esc}':fontsize=18:"
            "fontcolor=white@0.85:borderw=1:bordercolor=black@0.6:"
            "x=w-text_w-12:y=h-text_h-12"
        )
    if not filters:
        shutil.copyfile(video_path, out)
    else:
        run(["ffmpeg", "-y", "-i", video_path, "-vf", ",".join(filters),
             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "copy", out])
    return out


def plan_job(target_url, face_url, order, position, model, subtitles_url):
    """Generate the exact Actions inputs JSON for a swap job."""
    if not target_url or not face_url:
        raise gr.Error("Both a video URL and a face photo URL are needed.")
    if not target_url.startswith("http") or not face_url.startswith("http"):
        raise gr.Error("URLs must start with http(s).")
    plan = {
        "target_video_url": target_url.strip(),
        "source_face_url": face_url.strip(),
        "face_selector_order": order,
        "reference_face_position": position,
        "swapper_model": model,
        "pixel_boost": "256x256",
        "use_face_enhancer": "true",
        "face_mask_types": "box occlusion",
        "subtitles_url": (subtitles_url or "").strip(),
        "watermark_text": "AI-GENERATED DEMO",
        "consent_confirm": True,
    }
    pretty = json.dumps(plan, indent=2)
    link = REPO_ACTIONS
    md = (
        "### Your swap plan (paste-ready)\n\n"
        "1. Open **Actions → 02 · Simple Swap → Run workflow** "
        f"[here]({link}).\n"
        "2. Tick **consent_confirm** (you confirm everyone pictured agreed).\n"
        "3. Copy each value below into the matching field.\n"
        "4. Download the result from the run's **Artifacts** tab.\n"
    )
    return md, pretty


with gr.Blocks(title="Sema — free video localization studio") as demo:
    gr.Markdown(
        "# Sema — say it in your video\n"
        "Free video localization for Kenyan creators: swap a face, burn "
        "Swahili subtitles, stamp an AI label. Heavy compute runs free on "
        "GitHub Actions — this demo does the lightweight finishing here."
    )

    with gr.Tab("Finish a video"):
        gr.Markdown(
            "Upload any MP4 + optional `.srt` subtitles. "
            "You get back the video with subtitles burned in and a "
            "permanent **AI-GENERATED** corner label."
        )
        with gr.Row():
            vid = gr.Video(label="Video (mp4/mov/webm)", sources=["upload"])
            srt = gr.File(label="Subtitles (.srt, optional)", file_types=[".srt"])
        with gr.Row():
            label_in = gr.Textbox(label="Corner label", value="AI-GENERATED DEMO")
            go_btn = gr.Button("Finish video", variant="primary")
        out_vid = gr.Video(label="Finished video")
        go_btn.click(finish_demo, [vid, srt, label_in], out_vid)

    with gr.Tab("Plan a face-swap"):
        gr.Markdown(
            "Fill this form, get the exact inputs for the free GPU-less "
            "swap pipeline, then launch it on GitHub Actions."
        )
        t_url = gr.Textbox(label="Target video URL (direct mp4 link)")
        f_url = gr.Textbox(label="New face photo URL (direct jpg/png link)")
        with gr.Row():
            order = gr.Dropdown(
                ["left-right", "right-left", "best", "all"],
                value="left-right", label="Subject order")
            pos = gr.Number(value=0, precision=0, label="Subject index (0-based)")
            model = gr.Dropdown(
                ["inswapper_128", "hyperswap_1a_256"],
                value="inswapper_128", label="Swapper model")
        s_url = gr.Textbox(label="Subtitles URL, optional (direct .srt link)")
        plan_btn = gr.Button("Generate my swap plan", variant="primary")
        plan_md = gr.Markdown()
        plan_json = gr.Code(language="json", label="Inputs JSON")
        plan_btn.click(plan_job, [t_url, f_url, order, pos, model, s_url],
                       [plan_md, plan_json])

    with gr.Accordion("Consent & ethics", open=False):
        gr.Markdown(
            "- Only swap faces of people who **agreed** to it.\n"
            "- Every Sema output carries a baked-in **AI-GENERATED** label.\n"
            "- No political disinformation, no sexual content, no fraud.\n"
            "- Label anything you publish as synthetic."
        )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860)
