"""
app.py — A single-file Python web app (Flask + embedded frontend).
Run:  pip install flask && python app.py
Then open: http://localhost:5000
"""

from flask import Flask, jsonify, request, Response, g
import datetime
import logging
import os
import socket
import sys
import time
import uuid

app = Flask(__name__)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger(__name__)


@app.before_request
def start_request_log():
    g.request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    g.start_time = time.perf_counter()


@app.after_request
def finish_request_log(response):
    duration_ms = (time.perf_counter() - g.start_time) * 1000
    response.headers["X-Request-ID"] = g.request_id
    response.headers["Access-Control-Allow-Origin"] = os.getenv("CORS_ORIGIN", "*")
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Request-ID"
    logger.info(
        "request_id=%s remote_addr=%s method=%s path=%s status=%s duration_ms=%.2f",
        g.request_id,
        request.headers.get("X-Forwarded-For", request.remote_addr),
        request.method,
        request.full_path.rstrip("?"),
        response.status_code,
        duration_ms,
    )
    return response


@app.errorhandler(Exception)
def log_unhandled_exception(error):
    logger.exception("request_id=%s unhandled_error=%s", getattr(g, "request_id", "-"), error)
    return jsonify({"error": "internal server error", "request_id": getattr(g, "request_id", "-")}), 500

# ── tiny in-memory "database" ────────────────────────────────────────────────
_notes: list[dict] = [
    {"id": 1, "text": "Welcome to your notes app!", "ts": "just now"},
]
_next_id = 2


# ── API routes ────────────────────────────────────────────────────────────────
@app.get("/api/notes")
def get_notes():
    return jsonify(_notes)


@app.post("/api/notes")
def add_note():
    global _next_id
    body = request.get_json(silent=True) or {}
    text = (body.get("text") or "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    note = {
        "id": _next_id,
        "text": text,
        "ts": datetime.datetime.now().strftime("%b %d, %H:%M"),
    }
    _notes.append(note)
    _next_id += 1
    return jsonify(note), 201


@app.delete("/api/notes/<int:note_id>")
def delete_note(note_id):
    global _notes
    before = len(_notes)
    _notes = [n for n in _notes if n["id"] != note_id]
    if len(_notes) == before:
        return jsonify({"error": "not found"}), 404
    return jsonify({"deleted": note_id})


# ── health endpoint ───────────────────────────────────────────────────────────
@app.get("/api/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "time": datetime.datetime.now().isoformat(),
            "hostname": socket.gethostname(),
            "listening_on": f"{os.getenv('HOST', '0.0.0.0')}:{int(os.getenv('PORT', '5000'))}",
            "request_id": getattr(g, "request_id", "-"),
        }
    )


# ── FRONTEND (served from Python — no separate build step!) ───────────────────
HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Notes — all-in-one</title>
<link rel="preconnect" href="https://fonts.googleapis.com"/>
<link rel="stylesheet"
  href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700&family=DM+Mono:wght@400;500&display=swap"/>
<style>
  /* ── reset & tokens ─────────────────────────────────────────────── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --ink:    #1a1a18;
    --paper:  #f5f0e8;
    --cream:  #ede8dc;
    --accent: #c84b31;
    --muted:  #7a7568;
    --shadow: rgba(26,26,24,.12);
    --mono:   "DM Mono", monospace;
    --serif:  "Playfair Display", Georgia, serif;
    --radius: 4px;
    --tx:     all .2s ease;
  }

  body {
    background: var(--paper);
    color: var(--ink);
    font-family: var(--mono);
    font-size: 14px;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 48px 16px 80px;
    background-image:
      radial-gradient(circle at 80% 10%, #e8d9c0 0%, transparent 55%),
      radial-gradient(circle at 10% 90%, #ddd5c2 0%, transparent 50%);
  }

  /* ── header ────────────────────────────────────────────────────── */
  header {
    width: 100%; max-width: 640px;
    display: flex; justify-content: space-between; align-items: baseline;
    border-bottom: 2px solid var(--ink);
    padding-bottom: 12px; margin-bottom: 36px;
  }
  header h1 {
    font-family: var(--serif); font-size: clamp(28px,5vw,40px);
    letter-spacing: -.5px;
  }
  header span {
    font-size: 11px; color: var(--muted); letter-spacing: .08em;
    text-transform: uppercase;
  }
  #status-dot {
    display: inline-block; width: 7px; height: 7px;
    border-radius: 50%; background: #aaa;
    margin-right: 6px; transition: background .4s;
  }
  #status-dot.ok { background: #5cb85c; }

  /* ── compose box ───────────────────────────────────────────────── */
  .compose {
    width: 100%; max-width: 640px;
    display: flex; gap: 8px; margin-bottom: 32px;
  }
  .compose textarea {
    flex: 1; resize: none; height: 72px;
    background: var(--cream); border: 1.5px solid var(--ink);
    border-radius: var(--radius); padding: 12px;
    font-family: var(--mono); font-size: 14px; color: var(--ink);
    outline: none; transition: var(--tx);
    box-shadow: 3px 3px 0 var(--ink);
  }
  .compose textarea:focus { background: #fff; }
  .compose button {
    align-self: flex-end;
    background: var(--ink); color: var(--paper);
    border: none; border-radius: var(--radius);
    padding: 12px 20px; font-family: var(--mono);
    font-size: 13px; font-weight: 500; cursor: pointer;
    box-shadow: 3px 3px 0 var(--accent);
    transition: var(--tx); white-space: nowrap;
  }
  .compose button:hover {
    transform: translate(-1px,-1px);
    box-shadow: 4px 4px 0 var(--accent);
  }
  .compose button:active { transform: translate(1px,1px); box-shadow: 1px 1px 0 var(--accent); }

  /* ── notes list ────────────────────────────────────────────────── */
  #notes-list { width: 100%; max-width: 640px; display: flex; flex-direction: column; gap: 12px; }

  .note {
    background: #fff; border: 1.5px solid var(--ink);
    border-radius: var(--radius); padding: 16px 16px 12px;
    box-shadow: 3px 3px 0 var(--ink);
    display: flex; justify-content: space-between; align-items: flex-start;
    animation: slide-in .25s ease;
  }
  @keyframes slide-in {
    from { opacity: 0; transform: translateY(-8px); }
    to   { opacity: 1; transform: translateY(0); }
  }
  .note-body { flex: 1; }
  .note-text { line-height: 1.55; white-space: pre-wrap; word-break: break-word; }
  .note-ts   { font-size: 11px; color: var(--muted); margin-top: 8px; letter-spacing: .05em; }

  .delete-btn {
    background: none; border: none; cursor: pointer;
    color: var(--muted); font-size: 18px; line-height: 1;
    padding: 0 0 0 12px; transition: color .15s;
    flex-shrink: 0; margin-top: -2px;
  }
  .delete-btn:hover { color: var(--accent); }

  .empty { color: var(--muted); font-size: 13px; text-align: center; margin-top: 24px; }

  /* ── footer ────────────────────────────────────────────────────── */
  footer {
    margin-top: 56px; font-size: 11px; color: var(--muted);
    letter-spacing: .06em; text-align: center;
  }
  footer code {
    background: var(--cream); border: 1px solid #ccc;
    padding: 1px 5px; border-radius: 3px;
  }
</style>
</head>
<body>

<header>
  <h1>Notes</h1>
  <span><span id="status-dot"></span><span id="status-label">checking…</span></span>
</header>

<div class="compose">
  <textarea id="note-input" placeholder="Write a note…" rows="3"></textarea>
  <button id="add-btn" onclick="addNote()">+ Add</button>
</div>

<div id="notes-list"></div>

<footer>
  All data lives in-memory · API at <code>/api/notes</code> · one-file Python app
</footer>

<script>
const API = "/api";

/* ── health ping ──────────────────────────────────────────────── */
async function pingHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const dot = document.getElementById("status-dot");
    const lbl = document.getElementById("status-label");
    if (r.ok) {
      dot.className = "ok"; lbl.textContent = "server ok";
    } else throw new Error();
  } catch {
    document.getElementById("status-label").textContent = "server down";
  }
}

/* ── fetch & render ──────────────────────────────────────────── */
async function loadNotes() {
  const r = await fetch(`${API}/notes`);
  const notes = await r.json();
  render(notes);
}

function render(notes) {
  const list = document.getElementById("notes-list");
  if (!notes.length) {
    list.innerHTML = '<p class="empty">No notes yet — add one above ✦</p>';
    return;
  }
  // newest first
  list.innerHTML = [...notes].reverse().map(n => `
    <div class="note" id="note-${n.id}">
      <div class="note-body">
        <div class="note-text">${escHtml(n.text)}</div>
        <div class="note-ts">${n.ts}</div>
      </div>
      <button class="delete-btn" onclick="deleteNote(${n.id})" title="Delete">✕</button>
    </div>
  `).join("");
}

/* ── add ─────────────────────────────────────────────────────── */
async function addNote() {
  const ta = document.getElementById("note-input");
  const text = ta.value.trim();
  if (!text) { ta.focus(); return; }
  const btn = document.getElementById("add-btn");
  btn.disabled = true; btn.textContent = "…";
  try {
    const r = await fetch(`${API}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    if (!r.ok) throw new Error();
    ta.value = "";
    await loadNotes();
  } finally {
    btn.disabled = false; btn.textContent = "+ Add"; ta.focus();
  }
}

/* ── delete ──────────────────────────────────────────────────── */
async function deleteNote(id) {
  const el = document.getElementById(`note-${id}`);
  if (el) { el.style.opacity = ".4"; el.style.pointerEvents = "none"; }
  await fetch(`${API}/notes/${id}`, { method: "DELETE" });
  await loadNotes();
}

/* ── keyboard shortcut (Ctrl/Cmd+Enter) ─────────────────────── */
document.getElementById("note-input").addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) addNote();
});

/* ── escape helper ───────────────────────────────────────────── */
function escHtml(s) {
  return s.replace(/&/g,"&amp;").replace(/</g,"&lt;")
          .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

/* ── init ────────────────────────────────────────────────────── */
pingHealth();
loadNotes();
</script>
</body>
</html>"""


@app.get("/")
def index():
    return Response(HTML, mimetype="text/html")


# ── run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "5000"))
    debug = os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    logger.info("Starting app on http://%s:%s debug=%s", host, port, debug)
    app.run(host=host, port=port, debug=debug)
