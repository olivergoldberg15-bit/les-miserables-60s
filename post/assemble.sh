#!/usr/bin/env bash
set -euo pipefail
trap 'echo "[assemble] failed at line $LINENO" >&2' ERR
frames="${1:-build/frames}"
output="${2:-build/lesmis.mp4}"
assets="${ASSET_DIR:-build/assets}"
test -s audio/mix.wav || { echo '[assemble] required audio/mix.wav is missing' >&2; exit 1; }
python post/captions.py
# Reject missing frames before ffmpeg can silently truncate at a gap.
python - "$frames" <<'PY'
import json, math, pathlib, sys
count = math.ceil(json.loads(pathlib.Path('data/timing.json').read_text())['duration'] * 24)
missing = [i for i in range(1, count + 1) if not (pathlib.Path(sys.argv[1]) / f'{i:06d}.png').is_file()]
if missing:
    raise SystemExit(f'[assemble] missing {len(missing)} frames: {missing[:20]}')
PY
mkdir -p "$(dirname "$output")"
ffmpeg -hide_banner -y -framerate 24 -start_number 1 -i "$frames/%06d.png" \
  -i audio/mix.wav \
  -vf "noise=alls=3:allf=t+u:all_seed=1815,vignette=PI/5,subtitles=build/captions.ass:fontsdir='$assets/fonts'" \
  -map 0:v:0 -map 1:a:0 -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -af apad -shortest -movflags +faststart "$output"
