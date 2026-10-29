"""B3 corpus step 6: fetch the tracks of a list by HTTP range reads out of the remote fma_full zip.

usage: corpus_download.py LIST_CSV [WORKERS]   (LIST_CSV has an `id` and a `member` column)
Resumable: a finished file is skipped, a partial one (.part) is fetched again. zipfile checks the CRC of every member.
Appends to downloads.log (one JSON line per file) and prints a progress line every 60 s.
Stops (exit 3) when the bytes on disk pass LIMIT_GB.
"""
import io
import json
import os
import sys
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

URL = "https://os.unil.cloud.switch.ch/fma/fma_full.zip"
OUT = "/secondary/hyst-data/brain/corpus/"
AUDIO = OUT + "audio/"
LIMIT_GB = 40.0
BLOCK = 2 * 1024 * 1024


class RangeFile(io.RawIOBase):
    """Seekable read-only view of a remote file (206 responses)."""

    def __init__(self, url):
        self.s = requests.Session()
        self.url = url
        h = self.s.head(url, allow_redirects=True)
        h.raise_for_status()
        self.size = int(h.headers["Content-Length"])
        self.pos = 0
        self.buf = (0, b"")
        self.bytes = 0

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n < 0:
            n = self.size - self.pos
        n = min(n, self.size - self.pos)
        if n <= 0:
            return b""
        a, data = self.buf
        if not (a <= self.pos and self.pos + n <= a + len(data)):
            a = self.pos
            for attempt in range(6):
                try:
                    r = self.s.get(self.url, headers={"Range": f"bytes={a}-{min(self.size, a + max(n, BLOCK)) - 1}"}, timeout=60)
                    assert r.status_code == 206, r.status_code
                    break
                except Exception:
                    if attempt == 5:
                        raise
                    time.sleep(2 ** attempt)
            data = r.content
            self.bytes += len(data)
            self.buf = (a, data)
        out = data[self.pos - a:self.pos - a + n]
        self.pos += len(out)
        return out

    def readinto(self, b):
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


_local = threading.local()


def zip_for_thread():
    if not hasattr(_local, "zf"):
        _local.rf = RangeFile(URL)
        _local.zf = zipfile.ZipFile(_local.rf)
    return _local.zf


def fetch(member):
    path = AUDIO + os.path.basename(member)
    if os.path.exists(path):
        return path, 0, 0.0, "have"
    t0 = time.time()
    zf = zip_for_thread()
    data = zf.read(member)  # CRC checked here
    with open(path + ".part", "wb") as f:
        f.write(data)
    os.replace(path + ".part", path)
    return path, len(data), time.time() - t0, "new"


def disk_bytes():
    """Bytes of finished files only (.part files are in flight and may vanish)."""
    n = 0
    for f in os.listdir(AUDIO):
        if f.endswith(".mp3"):
            try:
                n += os.path.getsize(AUDIO + f)
            except FileNotFoundError:
                pass
    return n


def main():
    lst = pd.read_csv(sys.argv[1])
    workers = int(sys.argv[2]) if len(sys.argv) > 2 else 4
    os.makedirs(AUDIO, exist_ok=True)
    for f in os.listdir(AUDIO):
        if f.endswith(".part"):
            os.remove(AUDIO + f)      # truncated by an earlier stop; never counted as done
    members = list(lst["member"])
    done = [0, 0, 0]  # files, bytes, have
    t0 = time.time()
    lock = threading.Lock()
    stop = threading.Event()
    log = open(OUT + "downloads.log", "a")

    def job(m):
        if stop.is_set():
            return
        for attempt in range(4):
            try:
                path, n, dt, how = fetch(m)
                break
            except Exception as e:
                with lock:
                    log.write(json.dumps({"member": m, "attempt": attempt, "error": repr(e)[:200]}) + "\n"); log.flush()
                if hasattr(_local, "zf"):
                    del _local.zf     # fresh connection and directory next time
                time.sleep(5 * (attempt + 1))
        else:
            return
        with lock:
            done[0] += 1
            done[1] += n
            done[2] += how == "have"
            log.write(json.dumps({"member": m, "bytes": n, "seconds": round(dt, 2), "how": how}) + "\n"); log.flush()
            have = disk_bytes() if done[0] % 50 == 0 else 0
            if have > LIMIT_GB * 1e9:
                stop.set()

    def report():
        while not stop.is_set() and done[0] < len(members):
            time.sleep(60)
            el = time.time() - t0
            rate = done[1] / el / 1e6
            left = (len(members) - done[0]) / max(done[0] - done[2], 1) * el if done[0] > done[2] else float("nan")
            print(f"{time.strftime('%H:%M:%S')} files {done[0]}/{len(members)} new {done[1] / 1e9:.2f} GB {rate:.2f} MB/s eta {left / 3600:.1f} h", flush=True)

    threading.Thread(target=report, daemon=True).start()
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(job, members))
    print(f"finished files {done[0]}/{len(members)} new bytes {done[1]} in {time.time() - t0:.0f} s; stopped_by_limit={stop.is_set()}", flush=True)
    return 3 if stop.is_set() else 0


if __name__ == "__main__":
    sys.exit(main())
