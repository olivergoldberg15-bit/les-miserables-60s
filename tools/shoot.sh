#!/bin/bash
# Foreground headless screenshot of a lookdev URL (no visible window: Chrome inherits this shell's hidden console).
# usage: tools/shoot.sh <out.png> "<query string for tools/lookdev.html>"
# Needs the project synced to %LOCALAPPDATA%/Temp/lm and served on 127.0.0.1:8765.
CH="$(cygpath -u "$LOCALAPPDATA")/ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe"
OUT="$(cygpath -w "$1")"
timeout 60 "$CH" --headless --use-angle=swiftshader --enable-unsafe-swiftshader --hide-scrollbars \
  --window-size=1280,720 --virtual-time-budget=20000 --enable-logging=stderr --v=0 \
  --screenshot="$OUT" "http://127.0.0.1:8765/tools/lookdev.html?$2" 2>&1 \
  | grep -i -E "CONSOLE|Uncaught|Error" | grep -v -i -E "gpu|swiftshader|dbus|sandbox|fontconfig" | head -5
