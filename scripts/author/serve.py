#!/usr/bin/env python3
"""Local static server with HTTP Range support (audio seeking). usage: serve.py [DIR] [PORT]  (defaults: the build dir, 8765)."""
import http.server
import os
import re
import sys


class Handler(http.server.SimpleHTTPRequestHandler):
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
