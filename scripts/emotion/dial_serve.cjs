'use strict';
// dial_serve.cjs [DIR] [PORT]: serve the whole-song dial page on 127.0.0.1 with byte ranges.
// Only dial.html and song1.m4a, song2.m4a, song3.m4a are served; everything else in DIR
// (dial.json among it) answers 404. DIR defaults to this file's folder, PORT to 8778.
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(process.argv[2] || __dirname), port = Number(process.argv[3] || 8778);
const allowed = /^\/(dial\.html|song[123]\.m4a)$/;
http.createServer((req, res) => {
  let p;
  try { p = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); } catch { res.writeHead(400).end(); return; }
  if (p === '/') p = '/dial.html';
  if (!['GET', 'HEAD'].includes(req.method) || !allowed.test(p)) { res.writeHead(404).end(); return; }
  const file = path.join(root, p);
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404).end(); return; }
    const h = { 'Content-Type': p.endsWith('.html') ? 'text/html; charset=utf-8' : 'audio/mp4', 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store' };
    let start = 0, end = st.size - 1, status = 200;
    const m = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range || '');
    if (req.headers.range) {
      if (!m || (!m[1] && !m[2])) { res.writeHead(416, { 'Content-Range': `bytes */${st.size}` }).end(); return; }
      if (!m[1]) start = Math.max(0, st.size - Number(m[2]));
      else { start = Number(m[1]); if (m[2]) end = Math.min(Number(m[2]), end); }
      if (start > end) { res.writeHead(416, { 'Content-Range': `bytes */${st.size}` }).end(); return; }
      status = 206; h['Content-Range'] = `bytes ${start}-${end}/${st.size}`;
    }
    res.writeHead(status, { ...h, 'Content-Length': end - start + 1 });
    if (req.method === 'HEAD') { res.end(); return; }
    const s = fs.createReadStream(file, { start, end }); s.on('error', () => res.destroy()); res.on('close', () => s.destroy()); s.pipe(res);
  });
}).listen(port, '127.0.0.1', () => console.log(`Whole-song dial: http://127.0.0.1:${port}/dial.html`));
