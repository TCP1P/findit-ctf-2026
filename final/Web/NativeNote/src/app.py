import os
import re
import secrets
import sqlite3
import subprocess
import threading
import time
from collections import defaultdict
from threading import BoundedSemaphore, Lock

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, session, url_for)

app = Flask(__name__)

SECRET_PATH = "/tmp/.flask_secret"
if os.path.exists(SECRET_PATH):
    with open(SECRET_PATH, "rb") as f:
        app.secret_key = f.read()
else:
    app.secret_key = os.urandom(32)
    with open(SECRET_PATH, "wb") as f:
        f.write(app.secret_key)

DB_PATH = "/tmp/notes.db"
BOT_DIR = "/app/bot"
TMP_DIR = "/tmp/notes_output"
os.makedirs(TMP_DIR, exist_ok=True)

MAX_TITLE_LEN = 200
MAX_CONTENT_LEN = 32 * 1024
MAX_USERNAME_LEN = 64
MAX_PASSWORD_LEN = 128

MAX_CONCURRENT_REVIEWS = int(os.environ.get("MAX_CONCURRENT_REVIEWS", "4"))
REVIEW_SLOTS = BoundedSemaphore(MAX_CONCURRENT_REVIEWS)
REVIEW_SLOT_TIMEOUT = 60

REPORT_COOLDOWN_S = 20
_report_last = defaultdict(float)
_report_lock = Lock()

OUTPUT_TTL_S = 3600
JANITOR_INTERVAL_S = 600


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def init_db():
    with sqlite3.connect(DB_PATH) as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS notes (
                id       TEXT PRIMARY KEY,
                user_id  INTEGER NOT NULL,
                title    TEXT NOT NULL,
                content  TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );
        """)


def get_db():
    return sqlite3.connect(DB_PATH)


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            return render_template("register.html", error="All fields required")
        if len(username) > MAX_USERNAME_LEN or len(password) > MAX_PASSWORD_LEN:
            return render_template("register.html", error="Field too long")
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, password),
                )
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return render_template("register.html", error="Username already taken")
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        with get_db() as db:
            row = db.execute(
                "SELECT id FROM users WHERE username=? AND password=?",
                (username, password),
            ).fetchone()
        if row:
            session["user_id"] = row[0]
            session["username"] = username
            return redirect(url_for("notes"))
        return render_template("login.html", error="Invalid credentials")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Notes routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("notes"))


@app.route("/notes")
def notes():
    if "user_id" not in session:
        return redirect(url_for("login"))
    with get_db() as db:
        rows = db.execute(
            "SELECT id, title FROM notes WHERE user_id=?", (session["user_id"],)
        ).fetchall()
    return render_template("notes.html", notes=rows)


@app.route("/note/new", methods=["POST"])
def create_note():
    if "user_id" not in session:
        return abort(401)
    title = request.form.get("title", "Untitled")
    content = request.form.get("content", "")
    if len(title) > MAX_TITLE_LEN or len(content) > MAX_CONTENT_LEN:
        return abort(413)
    note_id = secrets.token_hex(10)
    with get_db() as db:
        db.execute(
            "INSERT INTO notes (id, user_id, title, content) VALUES (?, ?, ?, ?)",
            (note_id, session["user_id"], title, content),
        )
    return redirect(url_for("view_note", note_id=note_id))


@app.route("/note/<note_id>")
def view_note(note_id):
    with get_db() as db:
        row = db.execute(
            "SELECT title, content, user_id FROM notes WHERE id=?", (note_id,)
        ).fetchone()
    if not row:
        return abort(404)
    title, content, owner_id = row
    is_owner = session.get("user_id") == owner_id
    return render_template(
        "note.html",
        note_id=note_id,
        title=title,
        content=content,
        is_owner=is_owner,
    )


@app.route("/report", methods=["POST"])
def report():
    if "user_id" not in session:
        return abort(401)
    user_id = session["user_id"]

    note_id = request.form.get("id", "").strip()
    if not re.fullmatch(r"[0-9a-f]{20}", note_id):
        return abort(400)

    with get_db() as db:
        row = db.execute(
            "SELECT 1 FROM notes WHERE id=? AND user_id=?",
            (note_id, user_id),
        ).fetchone()
    if not row:
        return abort(404)

    now = time.time()
    with _report_lock:
        elapsed = now - _report_last[user_id]
        if elapsed < REPORT_COOLDOWN_S:
            wait = int(REPORT_COOLDOWN_S - elapsed) + 1
            return (f"Slow down — try again in {wait}s.", 429)
        _report_last[user_id] = now

    url = f"http://localhost:8080/note/{note_id}"
    threading.Thread(target=_run_review_pooled, args=(url,), daemon=True).start()
    return redirect(url_for("notes"))


def _run_review_pooled(url: str):
    if not REVIEW_SLOTS.acquire(timeout=REVIEW_SLOT_TIMEOUT):
        return
    try:
        _run_review(url)
    finally:
        REVIEW_SLOTS.release()


def _run_review(url: str):
    env = os.environ.copy()
    env["BOT_URL"] = url
    env["DISPLAY"] = ":99"
    electron_bin = os.path.join(BOT_DIR, "node_modules", ".bin", "electron")
    try:
        subprocess.run(
            [electron_bin, "--no-sandbox", "main.js"],
            cwd=BOT_DIR,
            env=env,
            timeout=35,
        )
    except Exception:
        pass


@app.route("/out/<path:filename>")
def serve_output(filename):
    if not re.fullmatch(r"[0-9a-f]{20}\.html", filename):
        return abort(403)
    return send_from_directory(TMP_DIR, filename)


def _janitor():
    while True:
        time.sleep(JANITOR_INTERVAL_S)
        cutoff = time.time() - OUTPUT_TTL_S
        try:
            for name in os.listdir(TMP_DIR):
                path = os.path.join(TMP_DIR, name)
                try:
                    if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                        os.unlink(path)
                except OSError:
                    pass
        except FileNotFoundError:
            pass
        with _report_lock:
            stale = [uid for uid, ts in _report_last.items()
                     if time.time() - ts > OUTPUT_TTL_S]
            for uid in stale:
                _report_last.pop(uid, None)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    threading.Thread(target=_janitor, daemon=True).start()
    app.run(host="0.0.0.0", port=8080, threaded=True)
