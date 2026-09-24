#!/usr/bin/env bash
# Build a Ken Burns demo clip from a still portrait — lets you test the whole
# pipeline with zero external media:
#
#   ./make_demo_clip.sh assets/samples/sample_face_A.jpg demo_target.mp4
#   # then run workflow 02 with source = any other face image
#
# The slow zoom/pan gives the clip just enough motion to prove the swap tracks
# movement, and the fully visible frontal face keeps detection trivial.

set -euo pipefail

SRC="${1:-assets/samples/sample_face_A.jpg}"
OUT="${2:-demo_target.mp4}"
DURATION="${3:-6}"
FPS="${4:-24}"

command -v ffmpeg >/dev/null || { echo "ffmpeg required" >&2; exit 1; }

# Fit the whole portrait into 1280x720 (pillarbox), then zoom gently (1.00 -> 1.08).
# Keeping the entire face in frame matters: face detectors fail on over-zoomed faces.
ffmpeg -y -v error -loop 1 -i "$SRC" -vf "
  scale=-2:720,
  pad=1280:720:(iw-ow)/2:0:color=gray,
  zoompan=z='min(1+0.0001*on,1.08)':d=${DURATION}*${FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720:fps=${FPS}
" -t "$DURATION" -pix_fmt yuv420p -c:v libx264 -preset veryfast -crf 20 "$OUT"

echo "demo clip: $OUT (${DURATION}s @ ${FPS}fps, 1280x720)"
