#!/usr/bin/env python3
"""Blind labelling tool for the hand-set dial study (WO28B, BRAIN_SPEC 7.43).  Stdlib only, no network.

  dialstudy_session.py --clips MANIFEST.json --out SESSION_DIR [--seed N]      build the session (once)
  dialstudy_session.py --out SESSION_DIR --serve [--port 8765]                 serve it on 127.0.0.1 and label

Build: each clip is hardlinked (or copied) under a random code name into SESSION_DIR/clips/, in a seeded random order.
The key (code -> manifest id, set, intent, effector, dials, seed) goes to SESSION_DIR/key/key.json; the server never
reads it and never serves it. The page shows one clip at a time, nothing but the clip, the buttons and n of N.
Set A-C items: one click from LABELS, optional note. Set D items (manifest entry with set "D" and "files": [a, b], two renders
of one excerpt): the two clips one after the other in random order, "first / second / neither".
Answers are appended at once to SESSION_DIR/answers.csv (code,answer,note,timestamp,replays); a reload resumes at the first
unanswered item. Manifest paths (file, files) are relative to the manifest's folder.
"""
import argparse, csv, json, os, random, re, secrets, shutil, sys, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

LABELS = ["tense", "heavy", "calm", "angry", "light", "nothing, glitching", "something, can't name it"]
PAIR_LABELS = ["first", "second", "neither"]
FIELDS = ["code", "answer", "note", "timestamp", "replays"]


def build(manifest_path, out, seed=None):
    manifest_path, out = Path(manifest_path), Path(out)
    if (out / "order.json").exists():
        raise SystemExit(f"{out} already holds a session")
    data = json.loads(manifest_path.read_text())
    clips = data["clips"] if isinstance(data, dict) else data
    seed = secrets.randbits(32) if seed is None else int(seed)
    rng = random.Random(seed)
    (out / "clips").mkdir(parents=True)
    (out / "key").mkdir()
    used = set()

    def code():
        while True:
            c = "c" + "".join(rng.choice("0123456789abcdef") for _ in range(4))
            if c not in used:
                used.add(c)
                return c

    def place(rel):
        src = (manifest_path.parent / rel).resolve()
        c = code()
        dst = out / "clips" / f"{c}.mp4"
        try:
            os.link(src, dst)
        except OSError:
            shutil.copyfile(src, dst)
        return c

    items, key = [], {}
    for clip in clips:
        meta = {k: clip.get(k) for k in ("id", "set", "intent", "effector", "dials")}
        if clip.get("set") == "D":
            first, second = list(clip["files"])
            if rng.random() < 0.5:
                first, second = second, first
            codes = [place(first), place(second)]
            item = {"code": code(), "kind": "pair", "clips": codes}
            key[item["code"]] = {**meta, "first": first, "second": second}
        else:
            c = place(clip["file"])
            item = {"code": c, "kind": "single", "clips": [c]}
            key[c] = meta
        items.append(item)
    rng.shuffle(items)
    (out / "key" / "key.json").write_text(json.dumps({"seed": seed, "key": key}, indent=1))
    (out / "order.json").write_text(json.dumps(items))
    (out / "answers.csv").write_text("")
    print(f"session built: {len(items)} items, seed {seed}, in {out}")


class Session:
    def __init__(self, out):
        self.out = Path(out)
        self.items = json.loads((self.out / "order.json").read_text())  # never the key
        self.lock = threading.Lock()
        self.path = self.out / "answers.csv"
        self.path.touch()

    def answered(self):
        with open(self.path, newline="") as f:
            return {r[0] for r in csv.reader(f) if r}

    def state(self):
        done = self.answered()
        todo = [i for i in self.items if i["code"] not in done]
        return {"total": len(self.items), "done": len(self.items) - len(todo), "item": (todo[0] if todo else None),
                "labels": LABELS, "pairLabels": PAIR_LABELS}

    def answer(self, body):
        code, ans, note = body.get("code"), body.get("answer"), str(body.get("note", ""))[:2000]
        with self.lock:
            item = next((i for i in self.items if i["code"] == code), None)
            allowed = PAIR_LABELS if item and item["kind"] == "pair" else LABELS
            if item is None or ans not in allowed:
                return 400
            if code in self.answered():
                return 409
            replays = max(0, int(body.get("replays", 0))) if str(body.get("replays", 0)).isdigit() else 0
            with open(self.path, "a", newline="") as f:
                csv.writer(f).writerow([code, ans, note, time.strftime("%Y-%m-%dT%H:%M:%S"), replays])
                f.flush(); os.fsync(f.fileno())
        return 200


PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Clips</title>
<style>
body{margin:0;background:#101418;color:#e6e6e6;font:18px system-ui,sans-serif;display:flex;flex-direction:column;align-items:center;gap:14px;padding:14px}
video{max-width:min(96vw,1280px);max-height:62vh;background:#000}
#bar{opacity:.6}button{font:inherit;padding:10px 16px;margin:4px;background:#26313c;color:inherit;border:1px solid #4a5b6b;border-radius:6px;cursor:pointer}
button:hover{background:#33424f}textarea{width:min(96vw,640px);height:3em;font:inherit;background:#1a2129;color:inherit;border:1px solid #4a5b6b}
#buttons{display:flex;flex-wrap:wrap;justify-content:center}
</style>
<div id=bar></div><div id=stage></div><div id=buttons></div>
<textarea id=note placeholder="note (optional)"></textarea>
<script>
let st, replays = 0, which = 0, vids = [];
const $ = id => document.getElementById(id);
async function load() {
  st = await (await fetch('/api/state')).json();
  if (!st.item) { $('bar').textContent = 'all ' + st.total + ' done, thank you'; $('stage').innerHTML = ''; $('buttons').innerHTML = ''; $('note').style.display = 'none'; return; }
  $('bar').textContent = (st.done + 1) + ' of ' + st.total;
  $('note').value = ''; replays = 0; which = 0;
  const it = st.item;
  $('stage').innerHTML = '';
  vids = it.clips.map(c => { const v = document.createElement('video'); v.src = '/clips/' + c + '.mp4'; v.muted = true; v.playsInline = true; v.controls = false; return v; });
  show(0);
  const labels = it.kind === 'pair' ? st.pairLabels : st.labels;
  $('buttons').innerHTML = '';
  if (it.kind === 'pair') { $('bar').textContent += ' (two clips: which one fits the music?)'; }
  const replay = document.createElement('button'); replay.textContent = it.kind === 'pair' ? 'play again from first' : 'replay';
  replay.onclick = () => { replays++; show(0); }; $('buttons').appendChild(replay);
  if (it.kind === 'pair') { const other = document.createElement('button'); other.textContent = 'show the other'; other.onclick = () => { replays++; show(which ? 0 : 1); }; $('buttons').appendChild(other); }
  labels.forEach(l => { const b = document.createElement('button'); b.textContent = l; b.onclick = () => send(it.code, l); $('buttons').appendChild(b); });
}
function show(i) {
  which = i; $('stage').innerHTML = ''; const v = vids[i]; v.currentTime = 0; $('stage').appendChild(v); v.play().catch(() => {});
  if (vids.length > 1 && i === 0) v.onended = () => show(1); else v.onended = null;
}
async function send(code, answer) {
  const r = await fetch('/api/answer', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ code, answer, note: $('note').value, replays }) });
  if (r.ok || r.status === 409) load();
}
load();
</script>"""


class Handler(BaseHTTPRequestHandler):
    session = None

    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/plain", extra=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            return self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        if path == "/api/state":
            return self._send(200, json.dumps(self.session.state()).encode(), "application/json")
        m = re.fullmatch(r"/clips/(c[0-9a-f]{4})\.mp4", path)
        if m and (self.session.out / "clips" / f"{m[1]}.mp4").is_file():
            return self._clip(self.session.out / "clips" / f"{m[1]}.mp4")
        self._send(404)

    def _clip(self, p):
        size = p.stat().st_size
        a, b = 0, size - 1
        rng = re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", ""))
        if rng and (rng[1] or rng[2]):
            if rng[1]:
                a = int(rng[1]); b = int(rng[2]) if rng[2] else b
            else:
                a = max(0, size - int(rng[2]))
            if a > b or a >= size:
                return self._send(416, extra={"Content-Range": f"bytes */{size}"})
            b = min(b, size - 1)
        with open(p, "rb") as f:
            f.seek(a); body = f.read(b - a + 1)
        extra = {"Accept-Ranges": "bytes"}
        if rng:
            extra["Content-Range"] = f"bytes {a}-{b}/{size}"
        self._send(206 if rng else 200, body, "video/mp4", extra)

    def do_POST(self):
        if self.path != "/api/answer":
            return self._send(404)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            return self._send(400)
        self._send(self.session.answer(body))


def make_server(out, port=8765):
    handler = type("H", (Handler,), {"session": Session(out)})
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--clips"); ap.add_argument("--out", required=True); ap.add_argument("--seed")
    ap.add_argument("--serve", action="store_true"); ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.clips:
        build(a.clips, a.out, a.seed)
    if a.serve or not a.clips:
        srv = make_server(a.out, a.port)
        print(f"open http://127.0.0.1:{srv.server_address[1]}/  (Ctrl-C to stop; answers are saved at once)")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
