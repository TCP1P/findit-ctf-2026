FROM node:20-bookworm

# ── System dependencies ────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip \
    xvfb \
    # Electron / Chromium runtime libs
    libgbm1 \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libasound2 \
    libxss1 \
    libxtst6 \
    libxrandr2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libx11-xcb1 \
    libxkbcommon0 \
    && rm -rf /var/lib/apt/lists/*

# ── Python / Flask ─────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt

# ── Preload webpack build ─────────────────────────────────────────────────
COPY bot/preload-src /app/bot/preload-src
WORKDIR /app/bot/preload-src
RUN npm install --prefer-offline
RUN npm run build

# ── Electron bot ──────────────────────────────────────────────────────────
COPY bot/package.json /app/bot/package.json
WORKDIR /app/bot
# Install Electron (downloads the binary)
RUN npm install --prefer-offline

# ── App source ────────────────────────────────────────────────────────────
WORKDIR /app
COPY app.py .
COPY templates ./templates
COPY static    ./static
COPY bot/main.js ./bot/main.js
COPY start.sh .
RUN chmod +x start.sh

# Flag is injected via environment variable at runtime
ENV FLAG="FINDIT{test_flag_replace_me}"

EXPOSE 8080
CMD ["/app/start.sh"]
