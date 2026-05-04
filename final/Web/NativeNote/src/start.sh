#!/bin/sh
set -e

# Write the flag to disk so the RCE can read it
echo "$FLAG" > /flag
chmod 444 /flag

# Start virtual framebuffer so Electron can render headlessly
Xvfb :99 -screen 0 1280x960x24 -ac &
export DISPLAY=:99

exec python3 /app/app.py
