"""serve.py POST /retune with retune.sh replaced by a stub: request checks, the mapping file it writes, the answer."""
import http.server
import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import serve


def post(port, obj, path="/retune"):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=json.dumps(obj).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.load(e)


class Retune(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        stub = self.dir / "stub.sh"
        stub.write_text('#!/bin/bash\necho "$@" > "$(dirname "$0")/args.txt"\ncat "$2" > /dev/null\necho /x/tuning/out-$1-$3-$4.mp4\n')
        stub.chmod(0o755)
        self.old_cwd, self.old_retune = os.getcwd(), serve.RETUNE
        os.chdir(self.dir)
        serve.RETUNE = stub
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), serve.Handler)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.port = self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        os.chdir(self.old_cwd)
        serve.RETUNE = self.old_retune

    def test_runs_the_loop_for_a_window(self):
        code, j = post(self.port, {"song": "presence", "mapping": {"name": "my map/../x", "version": 1}, "start": 61.7, "duration": 20})
        self.assertEqual(code, 200)
        self.assertEqual(j["url"], "tuning/out-presence-61-20.mp4")
        saved = self.dir / "tuning" / "work" / "my_map____x.json"       # the name is sanitised, nothing escapes tuning/work
        self.assertEqual(json.loads(saved.read_text())["version"], 1)
        args = (self.dir / "args.txt").read_text().split()
        self.assertEqual((args[0], args[2], args[3]), ("presence", "61", "20"))

    def test_rejects_bad_requests(self):
        for bad in ({"song": "nope", "mapping": {}, "start": 0}, {"song": "presence", "mapping": {}, "start": -1},
                    {"song": "presence", "mapping": {}, "start": 0, "duration": 500}, {"song": "presence"}):
            self.assertEqual(post(self.port, bad)[0], 400, bad)
        self.assertEqual(post(self.port, {}, "/other")[0], 404)


if __name__ == "__main__":
    unittest.main()
