FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        wget \
        build-essential \
        g++ \
        pkg-config \
        make \
        socat \
        python3 \
        zip unzip \
        python3-pip \
        socat \
        qemu-user \
        libunicorn-dev \
        # Cross compilers (C + C++)
        gcc-aarch64-linux-gnu g++-aarch64-linux-gnu \
        gcc-mips64-linux-gnuabi64 g++-mips64-linux-gnuabi64 \
        gcc-riscv64-linux-gnu g++-riscv64-linux-gnu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# copy all ctf work
COPY ./flag.txt ./main.py ./runner.cpp /app/

COPY ./unicorn.zip /tmp/
ADD --checksum=sha256:a9dddc2d6be5b72e71c9a4b52d6fd1c9d9b3d96ec9ccee7a7dd55900c067dec8 https://raw.githubusercontent.com/TCP1P/findit-ctf-2026/b2acbc235682c2754b3620518c873fd18f2bb92a/final/Pwn/tower-of-babel/src/unicorn.z01 /tmp/
ADD --checksum=sha256:84018691837242db728180fa7bc5a0b35ef03b709cac9e1e4480de247b502502 https://raw.githubusercontent.com/TCP1P/findit-ctf-2026/b2acbc235682c2754b3620518c873fd18f2bb92a/final/Pwn/tower-of-babel/src/unicorn.z02 /tmp/
RUN zip -s 0 /tmp/unicorn.zip --out /tmp/merged.zip \
    && unzip -q /tmp/merged.zip \
    && rm -f /tmp/unicorn.zip /tmp/unicorn.z01 /tmp/unicorn.z02 /tmp/merged.zip

RUN chmod -R go-rw .
RUN chmod 400 ./flag.txt

# create per-program users + one runner user
RUN useradd -u 1090 -M -r doctor && \
    useradd -u 1101 -M -r kaltsit && \
    useradd -u 1094 -M -r theresa && \
    useradd -u 1098 -M -r civilight_eterna
RUN useradd -u 1337 -m runner

COPY ./start.sh /app/start.sh
RUN chmod +x /app/start.sh
ENV PORT_LISTENER=1094
ENV TIMEOUT_DEVICE=300
EXPOSE 1094
CMD ["/app/start.sh"]

# RSCTF dynamic-flag compatibility layer. The build-time scan records
# exact marker-bearing files; runtime replacement is therefore bounded
# to those files instead of walking the image on every team start.
USER root
COPY rsctf-entrypoint.sh /usr/local/bin/rsctf-entrypoint
RUN set -eu; \
    chmod 0555 /usr/local/bin/rsctf-entrypoint; \
    : > /etc/rsctf-flag-targets; \
    for root in /app/start.sh /tmp /app /src /srv /home /opt /var/www /challenge /chall /ctf /root /usr/src /usr/local/bin /workspace /flag /flag.txt; do \
      if [ -e "$root" ]; then \
        find "$root" -xdev -type f ! -path /usr/local/bin/rsctf-entrypoint -exec grep -lF -e RSCTF_DYNAMIC_FLAG_9925133459743a65e579dc9 -e RSCTF_DYNAMIC_FLAG_c2bd0ee4b34e {} + >> /etc/rsctf-flag-targets 2>/dev/null || true; \
      fi; \
    done; \
    sort -u /etc/rsctf-flag-targets > /etc/rsctf-flag-targets.sorted; \
    mv /etc/rsctf-flag-targets.sorted /etc/rsctf-flag-targets; \
    while IFS= read -r target; do [ -f "$target" ] && chmod a+w "$target"; done < /etc/rsctf-flag-targets
ENTRYPOINT ["/usr/local/bin/rsctf-entrypoint"]
