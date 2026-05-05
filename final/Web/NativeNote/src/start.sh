#!/bin/sh
set -e

Xvfb :99 -screen 0 1280x960x24 -ac &
export DISPLAY=:99

exec python3 /app/app.py
