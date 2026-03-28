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
