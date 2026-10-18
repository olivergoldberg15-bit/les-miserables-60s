#!/bin/bash
# Stills at exact times, rendered from a short path (the session folder path is too long for HyperFrames on Windows).
# usage: tools/snap.sh <name> <t1,t2,...>     -> snaps/<name>/at-<t>s.png
# usage: tools/snap.sh --render <out.mp4>      -> full render into out/
set -e
SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST="$(cygpath -u "$LOCALAPPDATA")/Temp/lm"
mkdir -p "$DST"
MSYS_NO_PATHCONV=1 robocopy "$(cygpath -w "$SRC")" "$(cygpath -w "$DST")" /MIR /XD .git out snaps .hyperframes /NFL /NDL /NJH /NJS /NP >/dev/null || [ $? -lt 8 ]
cd "$DST"
if [ "$1" = "--render" ]; then
  npx -y hyperframes render . -o "out/$2" --fps 30 --workers 2
  mkdir -p "$SRC/out" && cp "out/$2" "$SRC/out/$2"
  exit 0
fi
NAME="$1"; AT="$2"
rm -rf "$DST/.hyperframes/snap-$NAME"
npx -y hyperframes snapshot . --at "$AT" --no-end --keep --timeout 60000 --describe false -o ".hyperframes/snap-$NAME" 2>&1 | grep -v "^\s*$" | tail -4
mkdir -p "$SRC/snaps/$NAME"
cp ".hyperframes/snap-$NAME"/*.png "$SRC/snaps/$NAME/" 2>/dev/null || true
ls "$SRC/snaps/$NAME"
