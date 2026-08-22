FROM ubuntu:latest
ENV DEBIAN_FRONTEND=noninteractive

# Install core dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    unzip \
    python3 \
    python3-pip \
    qemu-system-x86 \
    qemu-utils \
    python3 \
    python3-pip \
    python3-dev \
    curl \
    vim \
    socat \
    nano \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app

COPY ./run.sh ./start.sh ./image.zip ./
COPY ./flag.txt ./
COPY pow.py requirements.txt ./

# setup linux image
RUN unzip ./image.zip && rm -rf ./image.zip

# pow
RUN python3 -m pip install --no-cache-dir -r requirements.txt --break-system-packages

ENV PORT_LISTENER=31431
EXPOSE 31431
# Original final-stage ENTRYPOINT is wrapped by RSCTF at runtime.

# RSCTF dynamic-flag compatibility layer. The build-time scan records
# exact marker-bearing files; runtime replacement is therefore bounded
# to those files instead of walking the image on every team start.
USER root
COPY rsctf-entrypoint.sh /usr/local/bin/rsctf-entrypoint
RUN set -eu; \
    chmod 0555 /usr/local/bin/rsctf-entrypoint; \
    : > /etc/rsctf-flag-targets; \
    for root in /app /src /srv /home /opt /var/www /challenge /chall /ctf /root /usr/src /usr/local/bin /workspace /flag /flag.txt; do \
      if [ -e "$root" ]; then \
        find "$root" -xdev -type f ! -path /usr/local/bin/rsctf-entrypoint -exec grep -lF -e RSCTF_DYNAMIC_FLAG_2d5c55bcf323ae01ee5e370cc7fca32ddc7f9b957c7cf4edef3ff95db1a758cf -e RSCTF_DYNAMIC_FLAG_327f573c9dffdc958bb7436254883deaea07621d23d074b88d639 {} + >> /etc/rsctf-flag-targets 2>/dev/null || true; \
      fi; \
    done; \
    sort -u /etc/rsctf-flag-targets > /etc/rsctf-flag-targets.sorted; \
    mv /etc/rsctf-flag-targets.sorted /etc/rsctf-flag-targets; \
    while IFS= read -r target; do [ -f "$target" ] && chmod a+w "$target"; done < /etc/rsctf-flag-targets
ENTRYPOINT ["/usr/local/bin/rsctf-entrypoint", "bash", "./start.sh"]
