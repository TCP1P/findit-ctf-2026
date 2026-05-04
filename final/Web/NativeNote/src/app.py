import os
import re
import secrets
import sqlite3
import subprocess
import threading

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, session, url_for)

app = Flask(__name__)
app.secret_key = os.urandom(32)

FLAG = os.environ.get("FLAG", "FINDIT{test_flag_replace_me}")
DB_PATH = "/tmp/notes.db"
BOT_DIR = "/app/bot"
TMP_DIR = "/tmp/notes_output"

os.makedirs(TMP_DIR, exist_ok=True)


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
    note_id = secrets.token_hex(10)
    with get_db() as db:
        db.execute(
            "INSERT INTO notes (id, user_id, title, content) VALUES (?, ?, ?, ?)",
            (note_id, session["user_id"], title, content),
        )
    return redirect(url_for("view_note", note_id=note_id))


@app.route("/note/<note_id>")
def view_note(note_id):
    # Notes are public — no auth required (so the bot can view them directly)
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


# ---------------------------------------------------------------------------
# Report route — sends URL to the Electron admin bot
# ---------------------------------------------------------------------------

@app.route("/report", methods=["POST"])
def report():
    if "user_id" not in session:
        return abort(401)
    note_id = request.form.get("id", "").strip()
    if not re.fullmatch(r"[0-9a-f]{20}", note_id):
        return abort(400)
    # Verify note exists
    with get_db() as db:
        row = db.execute("SELECT 1 FROM notes WHERE id=?", (note_id,)).fetchone()
    if not row:
        return abort(404)

    url = f"http://localhost:8080/note/{note_id}"
    threading.Thread(target=_run_bot, args=(url,), daemon=True).start()
    return redirect(url_for("notes"))


def _run_bot(url: str):
    env = os.environ.copy()
    env["FLAG"] = FLAG
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
    except Exception as e:
        print(f"[bot error] {e}", flush=True)


# ---------------------------------------------------------------------------
# Exfil retrieval — bot writes flag here, player reads it back
# ---------------------------------------------------------------------------

@app.route("/out/<path:filename>")
def serve_output(filename):
    # Only .html files, no path traversal
    if not re.fullmatch(r"[0-9a-f]{20}\.html", filename):
        return abort(403)
    return send_from_directory(TMP_DIR, filename)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=8080, threaded=True)
