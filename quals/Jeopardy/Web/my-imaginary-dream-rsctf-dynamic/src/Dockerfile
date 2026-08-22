# Stage 1: Build the Go application
FROM golang:alpine AS builder

WORKDIR /app

COPY ./src/go.mod ./src/go.sum ./
RUN go mod download

COPY ./src/ .
RUN go build -o main .

# Stage 2: Set up Node.js and nginx
FROM node:21-alpine

# Environment variables
ENV LANG="C.UTF-8" PUPPETEER_SKIP_CHROMIUM_DOWNLOAD=true

# Update and install necessary packages including nginx and openssl
RUN apk update && \
    apk add --no-cache chromium openssl nginx

# Add a user for the app
RUN adduser -h /home/bot -D -u 10086 bot

# Clean yarn cache and remove unnecessary files
RUN yarn cache clean && \
    rm -rf /tmp/* /etc/apk/* /usr/share/man

# Generate self-signed certificate
WORKDIR /tmp

COPY ext.conf /tmp/ext.conf
RUN openssl req -x509 -newkey rsa:4096 -keyout /tmp/privkey.pem -out /tmp/fullchain.pem -days 365 -nodes -config ext.conf

WORKDIR /home/bot

# Copy package.json files and install dependencies
COPY ./bot/*.json .
RUN npm install

COPY ./bot .

# Set up nginx configuration
COPY ./nginx.conf /etc/nginx/nginx.conf

# Copy the built Go application from the builder stage
COPY --from=builder /app/main /usr/local/bin/main

COPY ./src/views ./views
COPY ./src/assets ./assets

# Switch to the bot user
USER root

# Start nginx and your Node.js application
CMD ["sh", "-c", "nginx & /usr/local/bin/main & node /home/bot/index.js"]
ENV APPURL=https://127.0.0.1:8080

# RSCTF dynamic-flag compatibility layer. The build-time scan records
# exact marker-bearing files; runtime replacement is therefore bounded
# to those files instead of walking the image on every team start.
USER root
COPY rsctf-entrypoint.sh /usr/local/bin/rsctf-entrypoint
RUN set -eu; \
    chmod 0555 /usr/local/bin/rsctf-entrypoint; \
    : > /etc/rsctf-flag-targets; \
    for root in /home/bot/assets /home/bot/views /usr/local/bin/main /etc/nginx/nginx.conf /tmp/ext.conf /home/bot /app /src /srv /home /opt /var/www /challenge /chall /ctf /root /usr/src /usr/local/bin /workspace /flag /flag.txt; do \
      if [ -e "$root" ]; then \
        find "$root" -xdev -type f ! -path /usr/local/bin/rsctf-entrypoint -exec grep -lF -e RSCTF_DYNAMIC_FLAG_d4bd06a1bc3910cbe6c35cc1 -e RSCTF_DYNAMIC_FLAG_8b2030b5a614f36b {} + >> /etc/rsctf-flag-targets 2>/dev/null || true; \
      fi; \
    done; \
    sort -u /etc/rsctf-flag-targets > /etc/rsctf-flag-targets.sorted; \
    mv /etc/rsctf-flag-targets.sorted /etc/rsctf-flag-targets; \
    while IFS= read -r target; do [ -f "$target" ] && chmod a+w "$target"; done < /etc/rsctf-flag-targets
ENTRYPOINT ["/usr/local/bin/rsctf-entrypoint"]
