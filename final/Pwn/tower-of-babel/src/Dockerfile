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

COPY ./unicorn.zip ./unicorn.z01 ./unicorn.z02 /tmp/
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
