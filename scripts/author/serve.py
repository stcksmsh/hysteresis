#!/usr/bin/env python3
"""Local static server with HTTP Range support (audio seeking) and POST /retune (the page's Render button -> retune.sh). usage: serve.py [DIR] [PORT]  (defaults: the build dir, 8765)."""
import http.server
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RETUNE = Path(__file__).resolve().parent / "retune.sh"
SONGS = ("instant-crush", "five-years", "presence")


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_POST(self):
        """POST /retune {song, mapping, start, duration}: save the mapping, run retune.sh for that window, answer {url, seconds}."""
        def reply(code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        try:
            if self.path != "/retune":
                return reply(404, {"error": "unknown path"})
            req = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            song, start, dur = req["song"], float(req["start"]), float(req.get("duration", 20))
            if song not in SONGS or not (start >= 0 and 0 < dur <= 120):
                return reply(400, {"error": "bad song, start or duration"})
            name = re.sub(r"[^A-Za-z0-9_-]", "_", str(req["mapping"].get("name") or "page"))[:40]
            work = Path(os.getcwd()) / "tuning" / "work"
            work.mkdir(parents=True, exist_ok=True)
            mp = work / f"{name}.json"
            mp.write_text(json.dumps(req["mapping"]))
            t0 = time.time()
            r = subprocess.run([str(RETUNE), song, str(mp), str(int(start)), str(int(dur))], capture_output=True, text=True, timeout=600)
            if r.returncode:
                return reply(500, {"error": (r.stderr or r.stdout)[-600:]})
            return reply(200, {"url": "tuning/" + Path(r.stdout.strip().splitlines()[-1]).name, "seconds": time.time() - t0})
        except (KeyError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as e:
            return reply(400, {"error": f"bad request: {e}"})

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        m = re.fullmatch(r"bytes=(\d*)-(\d*)", rng or "")
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        a, b = m.groups()
        start, end = (size - int(b), size - 1) if not a else (int(a), int(b) if b else size - 1)
        end = min(end, size - 1)
        if start > end:
            self.send_error(416)
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._left = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        left = getattr(self, "_left", None)
        if left is None:
            return super().copyfile(source, outputfile)
        while left > 0:
            chunk = source.read(min(65536, left))
            if not chunk:
                break
            outputfile.write(chunk)
            left -= len(chunk)
        self._left = None


if __name__ == "__main__":
    root = sys.argv[1] if len(sys.argv) > 1 else "/secondary/hyst-data/brain/author"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    os.chdir(root)
    print(f"http://127.0.0.1:{port}/index.html")
    http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
