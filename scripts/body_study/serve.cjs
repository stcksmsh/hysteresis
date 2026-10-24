'use strict';
// serve.cjs [DIR] [PORT]: serve the body-study answer page on 127.0.0.1 with byte ranges
// (seeking needs them). Only answer.html, test/{tNN,pN}-{a,b,c}.mp4 and test/practice.js
// are served; everything else in DIR (key.json among it) answers 404. DIR defaults to this file's folder.
const http = require('node:http'), fs = require('node:fs'), path = require('node:path');
const root = path.resolve(process.argv[2] || __dirname), port = Number(process.argv[3] || 8777);
const allowed = /^\/(answer\.html|test\/(t\d\d|p\d)-[abc]\.mp4|test\/practice\.js)$/;
http.createServer((req, res) => {
  let p;
  try { p = decodeURIComponent(new URL(req.url, 'http://localhost').pathname); } catch { res.writeHead(400).end(); return; }
  if (p === '/') p = '/answer.html';
  if (!['GET', 'HEAD'].includes(req.method) || !allowed.test(p)) { res.writeHead(404).end(); return; }
  const file = path.join(root, p);
  fs.stat(file, (err, st) => {
    if (err || !st.isFile()) { res.writeHead(404).end(); return; }
    const h = { 'Content-Type': p.endsWith('.html') ? 'text/html; charset=utf-8' : p.endsWith('.js') ? 'text/javascript' : 'video/mp4', 'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store' };
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
}).listen(port, '127.0.0.1', () => console.log(`Body study: http://127.0.0.1:${port}/answer.html`));
