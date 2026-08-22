#!/bin/bash
PORT=${PORT_LISTENER:-1094}
TIMEOUT=${TIMEOUT_DEVICE:-300}

while true; do
    socat TCP-LISTEN:${PORT},reuseaddr,fork \
        EXEC:"timeout ${TIMEOUT}s python3 /app/main.py",pty,stderr,ctty,setsid,echo=0
    sleep 1
done