#!/bin/sh
set -e

flag=${RSCTF_FLAG:-}
if [ -z "$flag" ] && [ -n "${RSCTF_FLAG_FILE:-}" ] && [ -r "$RSCTF_FLAG_FILE" ]; then
    flag=$(cat -- "$RSCTF_FLAG_FILE")
fi
if [ -z "$flag" ]; then
    echo "NativeNote requires RSCTF_FLAG or a readable RSCTF_FLAG_FILE" >&2
    exit 1
fi
printf '%s\n' "$flag" > /flag
chmod 0400 /flag
unset RSCTF_FLAG flag

Xvfb :99 -screen 0 1280x960x24 -ac &
export DISPLAY=:99

exec python3 /app/app.py
