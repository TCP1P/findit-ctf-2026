#!/bin/bash
while true; do
	socat TCP-LISTEN:$PORT_LISTENER,reuseaddr,fork EXEC:"bash /app/run.sh",pty,stderr,ctty,setsid
done