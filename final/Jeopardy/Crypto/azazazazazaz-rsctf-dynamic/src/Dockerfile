FROM sagemath/sagemath:latest

RUN sudo apt-get update && sudo apt install -y socat python3 python3-pip

RUN mkdir /home/sage/ctf
COPY ./requirements.txt /home/sage/ctf

RUN sage -sh -c "python3 -m pip install -r /home/sage/ctf/requirements.txt"

RUN mkdir /home/sage/ctf/src
COPY ./chall.py /home/sage/ctf/src
COPY ./flag.txt /home/sage/ctf/src
COPY ./run.sh /home/sage/ctf/src
RUN sudo chmod +x /home/sage/ctf/src/run.sh

WORKDIR /home/sage/ctf/src

CMD ["./run.sh"]

# RSCTF dynamic-flag compatibility layer. The build-time scan records
# exact marker-bearing files; runtime replacement is therefore bounded
# to those files instead of walking the image on every team start.
USER root
COPY rsctf-entrypoint.sh /usr/local/bin/rsctf-entrypoint
RUN set -eu; \
    chmod 0555 /usr/local/bin/rsctf-entrypoint; \
    : > /etc/rsctf-flag-targets; \
    for root in /home/sage/ctf /home/sage/ctf/src /app /src /srv /home /opt /var/www /challenge /chall /ctf /root /usr/src /usr/local/bin /workspace /flag /flag.txt; do \
      if [ -e "$root" ]; then \
        find "$root" -xdev -type f ! -path /usr/local/bin/rsctf-entrypoint -exec grep -lF -e RSCTF_DYNAMIC_FLAG_330fbd84c3847ad6e929e3a7aa119701301a1f66e5d858c1b18edc1afbcbca12330fbd84c3 -e RSCTF_DYNAMIC_FLAG_63683af1f7af3de99f89f0835f84751b8b6102939c653a68bb70801b2f9a2bd {} + >> /etc/rsctf-flag-targets 2>/dev/null || true; \
      fi; \
    done; \
    sort -u /etc/rsctf-flag-targets > /etc/rsctf-flag-targets.sorted; \
    mv /etc/rsctf-flag-targets.sorted /etc/rsctf-flag-targets; \
    while IFS= read -r target; do [ -f "$target" ] && chmod a+w "$target"; done < /etc/rsctf-flag-targets
ENTRYPOINT ["/usr/local/bin/rsctf-entrypoint"]
