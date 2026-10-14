// test_dial.cjs DIR URL: headless check of dial.html on three synthetic 4 s songs served
// by dial_serve.cjs; DIR has an empty dl/. Made by test_dial.sh. Never run on real data.
const puppeteer = require('/home/stcksmsh/Programming/Github/Hysteresis/node_modules/puppeteer-core');
const fs = require('fs'), T = process.argv[2], URL_ = process.argv[3];
const ok = (c, m) => { if (!c) throw Error('FAIL: ' + m); console.log('ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const STORE = 'hyst-emotion-dial-v1';
(async () => {
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox'] });
  try {
    const p = await b.newPage(); await p.setViewport({ width: 1366, height: 768 });
    const reqs = []; p.on('request', r => { if (r.url().startsWith('http')) reqs.push(new URL(r.url()).pathname); });
    p.on('pageerror', e => { throw Error('page error: ' + e.message); });
    const cdp = await p.createCDPSession();
    await cdp.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: T + '/dl' });
    await p.goto(URL_); await sleep(300);
    const ev = (f, ...a) => p.evaluate(f, ...a), txt = id => p.$eval('#' + id, e => e.textContent);
    const hidden = id => p.$eval('#' + id, e => e.hidden);
    const stored = () => ev(k => JSON.parse(localStorage.getItem(k) || 'null'), STORE);
    const nums = async () => { const m = /valence ([+-]\d\.\d\d)\narousal ([+-]\d\.\d\d)/.exec(await txt('nums')); return [Number(m[1]), Number(m[2])]; };
    const near = (x, y) => Math.abs(x[0] - y[0]) < 0.011 && Math.abs(x[1] - y[1]) < 0.011;
    async function moveTo(v, a) {
      const r = await ev(() => { const r = document.getElementById('pad').getBoundingClientRect(); return { l: r.left, t: r.top, w: r.width, h: r.height }; });
      await p.mouse.move(r.l + (v + 1) / 2 * r.w, r.t + (1 - a) / 2 * r.h, { steps: 3 }); await sleep(60);
    }
    const rgb = async () => { await sleep(50); const h = await p.$eval('#pad', e => e.dataset.tint); return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); };

    const fit = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, w: document.getElementById('pad').getBoundingClientRect().width }));
    ok(fit.sw <= fit.cw, `no horizontal scroll (${fit.sw} <= ${fit.cw})`);
    ok(Math.abs(fit.w - 520) < 1, `pad 520 px (${fit.w})`);
    ok((await txt('title')) === 'Song 1 of 3: Instant Crush (Daft Punk)', 'song 1 title shown');
    ok(near(await nums(), [0, 0]), 'starts at the centre');
    const c0 = await rgb(); ok(c0[0] === c0[1] && c0[1] === c0[2], `centre tint is grey (${c0})`);
    ok(!(await ev(() => document.getElementById('audio').controls)), 'audio has no controls');

    // Practice: pad works, nothing recorded.
    ok(!(await hidden('practice')), 'practice offered before song 1');
    await p.click('#practice');
    ok((await txt('status')).startsWith('Practice, not recorded: 30 s'), 'practice 30 s');
    await moveTo(0.5, 0.5); ok(near(await nums(), [0.5, 0.5]), 'pointer moves the marker, no button held');
    await moveTo(1, 0); let c = await rgb(); ok(c[0] > c[1] && c[0] > c[2], `pleasant edge tint red-hued (${c})`);
    await moveTo(0, 1); c = await rgb(); ok(c[1] > c[0] && c[0] > c[2], `top edge tint yellow-green (${c})`);
    await moveTo(-1, 0); c = await rgb(); ok(Math.abs(c[1] - c[2]) <= 1 && c[1] > c[0], `unpleasant edge tint cyan (${c})`);
    await moveTo(0, -1); c = await rgb(); ok(c[2] > c[0] && c[0] > c[1], `bottom edge tint violet (${c})`);
    await moveTo(0, -0.3); const cs = await rgb();
    ok(Math.max(...c) - Math.min(...c) > Math.max(...cs) - Math.min(...cs), `saturation grows with distance (${cs} vs ${c})`);
    const trail = await ev(() => trail.length); ok(trail > 3, `trail kept (${trail} points)`);
    await p.click('#endpractice'); await sleep(100);
    let s = await stored();
    ok(s.practiceDone && s.songs.every(x => x.samples.length === 0 && x.status === 'todo'), 'practice not recorded');
    ok(near(await nums(), [0, 0]) && (await hidden('practice')), 'after practice: centre, practice gone');
    ok(await ev(() => trail.every(q => performance.now() - q.ms < 3000)), 'trail holds only the last 3 s');

    // Song 1: sampling, pause, no seek, pointer, keys.
    await p.click('#start'); await sleep(150);
    ok(!(await hidden('pause')) && (await hidden('start')), 'playing: Pause shown, Start gone');
    await moveTo(-0.5, 0.5); const tP1 = await ev(() => audio.currentTime);
    await sleep(900);
    await moveTo(0.5, -0.5); const tP2 = await ev(() => audio.currentTime);
    await sleep(300);
    await ev(() => { audio.currentTime = 0; }); await sleep(250);
    let t = await ev(() => audio.currentTime); ok(t > tP2, `seek back undone (${t.toFixed(2)})`);
    await ev(() => { audio.currentTime = 3.6; }); await sleep(150);
    t = await ev(() => audio.currentTime); ok(t < 3, `seek forward undone (${t.toFixed(2)})`);
    const w = await p.$eval('#progbar', e => parseFloat(e.style.width)); ok(w > 20 && w < 70, `progress bar follows the song (${w}%)`);
    await p.click('#pause'); await sleep(100);
    const n1 = await ev(() => song.samples.length), a1 = await ev(() => audio.currentTime);
    s = await stored(); ok(s.songs[0].status === 'playing' && s.songs[0].samples.length > 5, `saved during the song (${s.songs[0].samples.length} samples)`);
    ok((await txt('pause')) === 'Resume' && (await txt('status')).startsWith('Paused'), 'Pause shows Resume');
    await sleep(900);
    ok(n1 === (await ev(() => song.samples.length)) && a1 === (await ev(() => audio.currentTime)), `pause stops recording (${n1} samples)`);
    await p.mouse.move(3, 3); await sleep(60);
    ok(near(await nums(), [0.5, -0.5]), 'pointer left the pad: marker stays');
    await p.click('#pause');
    await p.keyboard.press('ArrowLeft'); await p.keyboard.press('ArrowLeft'); await p.keyboard.press('ArrowUp');
    const tK = await ev(() => audio.currentTime); await sleep(100);
    const nk = await nums(); ok(near(nk, [0.4, -0.45]), `arrow keys nudge by 0.05 (${nk})`);
    while (!(await ev(() => mode === 'idle'))) await sleep(100);
    s = await stored(); const s1 = s.songs[0], d = s1.duration;
    ok(s1.status === 'done' && s1.endedAt, 'song 1 done and saved');
    ok(s1.samples.length === Math.floor(d * 10 + 1e-9) + 1, `one sample per 0.1 s of audio (${s1.samples.length} for ${d.toFixed(3)} s)`);
    ok(s1.samples.every(([x], k) => x === k / 10), 'sample times are k / 10 s on the audio clock');
    const at = (lo, hi) => s1.samples.filter(([x]) => x > lo && x < hi);
    ok(at(tP1 + 0.15, tP2 - 0.15).every(q => q[1] === -0.5 && q[2] === 0.5) && at(tP1 + 0.15, tP2 - 0.15).length >= 5, 'samples carry the first position');
    ok(at(tP2 + 0.15, tK - 0.15).every(q => q[1] === 0.5 && q[2] === -0.5), 'samples carry the second position');
    ok(at(tK + 0.15, 99).every(q => q[1] === 0.4 && q[2] === -0.45) && at(tK + 0.15, 99).length >= 3, 'samples carry the key position');
    const types = s1.events.map(e => e.type).join(',');
    ok(types === 'start,seekRefused,seekRefused,pause,resume,end', `events (${types})`);
    ok(Math.abs(s1.events[3].t - a1) < 0.01, 'pause event at the audio time');
    ok(!(await hidden('next')) && (await hidden('start')), 'Next song offered');
    await p.click('#next'); await sleep(100);
    ok((await txt('title')) === 'Song 2 of 3: Five Years (David Bowie)' && near(await nums(), [0, 0]), 'song 2 title, marker at centre');

    // Reload during song 2 restarts it; song 1 stays done.
    await p.click('#start'); await sleep(1300);
    await p.reload(); await sleep(400);
    s = await stored();
    ok(s.songs[0].status === 'done' && s.songs[0].samples.length === s1.samples.length, 'after reload: song 1 kept');
    ok(s.songs[1].status === 'todo' && s.songs[1].samples.length === 0 && s.songs[1].restarts.length === 1 && s.songs[1].restarts[0].reachedT > 0.5, `after reload: song 2 restarts (${JSON.stringify(s.songs[1].restarts[0])})`);
    ok((await txt('title')).startsWith('Song 2 of 3') && (await txt('status')).includes('starts again'), 'restart shown');
    ok(await hidden('practice'), 'practice not offered again');

    // Download, clear, load.
    await p.click('#download'); await sleep(700);
    const dl = JSON.parse(fs.readFileSync(T + '/dl/dial.json'));
    ok(JSON.stringify(dl) === JSON.stringify(s), 'download equals saved state');
    await ev(k => localStorage.removeItem(k), STORE); await p.reload(); await sleep(300);
    ok((await txt('title')).startsWith('Song 1 of 3'), 'cleared: back at song 1');
    await (await p.$('#load')).uploadFile(T + '/dl/dial.json'); await sleep(400);
    s = await stored();
    ok((await txt('title')).startsWith('Song 2 of 3') && s.songs[0].samples.length === s1.samples.length && s.songs[1].restarts.length === 1, 'load resumes from the file');
    fs.unlinkSync(T + '/dl/dial.json');

    // Songs 2 and 3 to the end.
    for (const k of [2, 3]) {
      await p.click('#start'); await sleep(200);
      while (!(await ev(() => mode === 'idle'))) await sleep(100);
      if (k === 2) { await p.click('#next'); await sleep(100); ok((await txt('title')) === 'Song 3 of 3: Presence (Justice)', 'song 3 title'); }
    }
    ok((await txt('title')).includes('all three songs done') && (await txt('status')).includes('/secondary/hyst-data/emotion/dial/dial.json'), 'end: where to put dial.json');
    ok(await hidden('start') && await hidden('next'), 'end: nothing more to play');
    await p.click('#download'); await sleep(700);
    const fin = JSON.parse(fs.readFileSync(T + '/dl/dial.json'));
    ok(fin.songs.every(x => x.status === 'done' && x.samples.length >= 40), 'final download: three songs done');
    ok(fin.songs[1].restarts.length === 1 && fin.songs[1].events[0].type === 'start', 'final download keeps the restart');
    const paths = [...new Set(reqs)].sort().join(' ');
    ok(paths === '/dial.html /song1.m4a /song2.m4a /song3.m4a', `only the page and the songs requested (${paths})`);
  } finally { await b.close(); }
})().catch(e => { console.error(e.message); process.exit(1); });
