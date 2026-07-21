#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
video_dir="$repo_root/submission/video"
build_dir="$video_dir/build"
tools_venv="${DATAHUB_VIDEO_TOOLS_VENV:-/tmp/datahub-video-tools}"
chrome="${CHROME_BIN:-/home/codex/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome}"

if [[ ! -x "$tools_venv/bin/edge-tts" ]]; then
  echo "Missing edge-tts in $tools_venv" >&2
  exit 1
fi
if [[ ! -x "$chrome" ]]; then
  echo "Missing Chromium at $chrome" >&2
  exit 1
fi

ffmpeg="$($tools_venv/bin/python -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')"
mkdir -p "$build_dir"

durations=(18 30 30 34 28 15)
segments=()

for number in 1 2 3 4 5 6; do
  padded="$(printf '%02d' "$number")"
  "$chrome" \
    --headless=new \
    --no-sandbox \
    --disable-gpu \
    --hide-scrollbars \
    --window-size=1280,720 \
    --screenshot="$build_dir/slide-$padded.png" \
    "file://$video_dir/index.html?slide=$number" >/dev/null 2>&1

  "$tools_venv/bin/edge-tts" \
    --voice en-GB-RyanNeural \
    --rate=-8% \
    --file "$video_dir/narration/$padded.txt" \
    --write-media "$build_dir/voice-$padded.mp3"

  duration="${durations[$((number - 1))]}"
  segment="$build_dir/segment-$padded.mp4"
  "$ffmpeg" -y \
    -loop 1 -framerate 30 -i "$build_dir/slide-$padded.png" \
    -i "$build_dir/voice-$padded.mp3" \
    -vf "scale=1280:720:flags=lanczos,format=yuv420p" \
    -af "adelay=750|750,apad=pad_dur=$duration" \
    -t "$duration" \
    -c:v libx264 -preset medium -crf 24 \
    -c:a aac -b:a 96k \
    -movflags +faststart \
    "$segment" >/dev/null 2>&1
  segments+=("$segment")
done

concat_file="$build_dir/segments.txt"
: > "$concat_file"
for segment in "${segments[@]}"; do
  printf "file '%s'\n" "$segment" >> "$concat_file"
done

"$ffmpeg" -y \
  -f concat -safe 0 -i "$concat_file" \
  -c copy -movflags +faststart \
  "$video_dir/datahub-contract-bridge-demo.mp4" >/dev/null 2>&1

echo "Rendered $video_dir/datahub-contract-bridge-demo.mp4"
