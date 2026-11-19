// test_dial.cjs DIR URL: headless check of dial.html (format 2) on three synthetic 4 s songs
// served by dial_serve.cjs; DIR has an empty dl/. Made by test_dial.sh. Never run on real data.
const puppeteer = require('/home/stcksmsh/Programming/Github/Hysteresis/node_modules/puppeteer-core');
const fs = require('fs'), T = process.argv[2], URL_ = process.argv[3];
const ok = (c, m) => { if (!c) throw Error('FAIL: ' + m); console.log('ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const STORE = 'hyst-emotion-dial-v2';
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
    const numsA = async () => { await sleep(80); const m = /^energy (\d\.\d\d)$/.exec(await txt('nums')); return Number(m[1]); };
    const numsB = async () => { await sleep(80); const m = /^light (\d\.\d\d)\nheavy (\d\.\d\d)$/.exec(await txt('nums')); return [Number(m[1]), Number(m[2])]; };
    const near = (x, y) => [x].flat().every((v, i) => Math.abs(v - [y].flat()[i]) < 0.011);
    const box = id => ev(id => { const r = document.getElementById(id).getBoundingClientRect(); return { l: r.left, t: r.top, w: r.width, h: r.height }; }, id);
    async function slide(e) { const r = await box('slider'); await p.mouse.move(r.l + r.w / 2, r.t + 1 + (1 - e) * (r.h - 2), { steps: 3 }); await sleep(60); }
    async function padTo(l, h) { const r = await box('pad'); await p.mouse.move(r.l + 1 + l * (r.w - 2), r.t + 1 + (1 - h) * (r.h - 2), { steps: 3 }); await sleep(60); }
    const rgb = async id => { await sleep(60); const h = await p.$eval('#' + id, e => e.dataset.tint); return [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16)); };
    const waitIdle = async () => { while (!(await ev(() => mode === 'idle'))) await sleep(100); };
    const cell = id => txt('state-' + id);

    // Picker.
    const fit = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
    ok(fit.sw <= fit.cw, `no horizontal scroll (${fit.sw} <= ${fit.cw})`);
    ok(!(await hidden('picker')) && (await hidden('rec')), 'starts at the picker');
    for (const id of ['A1', 'A2', 'A3', 'B1', 'B2', 'B3']) ok((await cell(id)) === 'not recorded', `${id} not recorded`);
    ok((await txt('pstatus')).includes('Done: 0 of 6') && (await txt('pstatus')).includes('/secondary/hyst-data/emotion/dial/dial2.json'), 'picker: done count and where the file goes');

    // Pass A on song 3 first: practice, then the song.
    await p.click('#go-A3'); await sleep(100);
    ok((await txt('title')) === 'Pass A, energy: Presence (Justice)', 'pass A title, song 3 picked first');
    ok(!(await hidden('wrapA')) && (await hidden('wrapB')), 'pass A shows the slider only');
    ok(await numsA() === 0, 'slider starts at 0');
    let c = await rgb('slider'); ok(c[0] === c[1] && c[1] === c[2], `tint neutral at 0 (${c})`);
    await p.click('#practice');
    ok((await txt('status')).startsWith('Practice, not recorded: 30 s'), 'practice 30 s');
    await slide(0.7); ok(near(await numsA(), 0.7), 'pointer moves the slider, no button held');
    await slide(1); const cA1 = await rgb('slider'); ok(cA1[0] > cA1[1] && cA1[1] > cA1[2], `tint warm at 1 (${cA1})`);
    await slide(0.4); const cA4 = await rgb('slider'); ok(cA4[0] > cA4[2] && cA4[0] - cA4[2] < cA1[0] - cA1[2], `tint follows the value (${cA4})`);
    await p.keyboard.press('Space'); await sleep(50);
    ok((await p.$eval('#slider', e => e.dataset.flash)) === '1', 'Space flashes in practice');
    await p.click('#endpractice'); await sleep(100);
    let s = await stored(); ok(s.practiceDone.A && !s.practiceDone.B && s.takes.length === 0, 'practice not recorded');

    await p.click('#start'); await sleep(150);
    ok(!(await hidden('pause')) && (await hidden('start')) && (await hidden('back')), 'playing: Pause shown, Start and Back gone');
    await slide(0.2); const tP1 = await ev(() => audio.currentTime);
    await sleep(800);
    await slide(0.8); const tP2 = await ev(() => audio.currentTime);
    await p.keyboard.press('Space'); const tTap = await ev(() => audio.currentTime); await sleep(40);
    ok((await p.$eval('#slider', e => e.dataset.flash)) === '1', 'tap flashes');
    const tk = await ev(() => [...document.querySelectorAll('.tick')].map(k => parseFloat(k.style.left)));
    ok(tk.length === 1 && Math.abs(tk[0] - 100 * tTap / 4) < 3, `tap tick on the progress bar (${tk})`);
    await sleep(200);
    await ev(() => { audio.currentTime = 0; }); await sleep(250);
    let t = await ev(() => audio.currentTime); ok(t > tP2, `seek back undone (${t.toFixed(2)})`);
    await ev(() => { audio.currentTime = 3.6; }); await sleep(150);
    t = await ev(() => audio.currentTime); ok(t < 3, `seek forward undone (${t.toFixed(2)})`);
    const w = await p.$eval('#progbar', e => parseFloat(e.style.width)); ok(w > 20 && w < 75, `progress bar follows the song (${w}%)`);
    await p.click('#pause'); await sleep(100);
    const n1 = await ev(() => take.samples.length), a1 = await ev(() => audio.currentTime);
    s = await stored(); ok(s.takes[0].status === 'playing' && s.takes[0].samples.length > 5, `saved during the song (${s.takes[0].samples.length} samples)`);
    ok((await txt('pause')) === 'Resume' && (await txt('status')).startsWith('Paused'), 'Pause shows Resume');
    await p.keyboard.press('Space');
    await sleep(800);
    ok(n1 === (await ev(() => take.samples.length)) && a1 === (await ev(() => audio.currentTime)), `pause stops recording (${n1} samples)`);
    ok((await ev(() => take.taps.length)) === 1, 'no tap while paused');
    ok((await txt('pause')) === 'Resume', 'Space does not press the focused Pause button');
    await p.mouse.move(3, 3); ok(near(await numsA(), 0.8), 'pointer left the slider: marker stays');
    await p.click('#pause');
    for (const k of ['ArrowUp', 'ArrowUp', 'ArrowDown', 'ArrowUp', 'ArrowLeft']) await p.keyboard.press(k);
    const tK = await ev(() => audio.currentTime);
    const nk = await numsA(); ok(near(nk, 0.9), `Up / Down keys nudge by 0.05, Left ignored (${nk})`);
    for (let k = 0; k < 3; k++) await p.keyboard.press('ArrowUp'); ok(near(await numsA(), 1), 'clamped at 1');
    const tK2 = await ev(() => audio.currentTime);
    await waitIdle();
    s = await stored(); let A = s.takes[0]; const d = A.duration;
    ok(A.status === 'done' && A.pass === 'A' && A.song === 'song3.m4a' && A.endedAt, 'take saved at the end');
    ok(A.samples.length === Math.floor(d * 10 + 1e-9) + 1, `one sample per 0.1 s of audio (${A.samples.length} for ${d.toFixed(3)} s)`);
    ok(A.samples.every(q => q.length === 2) && A.samples.every(([x], k) => x === k / 10), 'samples [t, energy], t = k / 10 s on the audio clock');
    const at = (smp, lo, hi) => smp.filter(([x]) => x > lo && x < hi);
    ok(at(A.samples, tP1 + 0.15, tP2 - 0.15).length >= 4 && at(A.samples, tP1 + 0.15, tP2 - 0.15).every(q => q[1] === 0.2), 'samples carry the first value');
    ok(at(A.samples, tP2 + 0.15, tK - 0.15).every(q => q[1] === 0.8), 'samples carry the second value');
    ok(at(A.samples, tK2 + 0.15, 99).length >= 3 && at(A.samples, tK2 + 0.15, 99).every(q => q[1] === 1), 'samples carry the key value');
    ok(A.taps.length === 1 && Math.abs(A.taps[0] - tTap) < 0.05, `tap saved at its audio time (${A.taps})`);
    let types = A.events.map(e => e.type).join(',');
    ok(types === 'start,seekRefused,seekRefused,pause,resume,end', `events (${types})`);
    ok(Math.abs(A.events[3].t - a1) < 0.01, 'pause event at the audio time');
    ok((await txt('status')).startsWith('Saved') && (await hidden('start')) && !(await hidden('back')), 'after the song: saved, Back offered');
    await p.click('#back'); await sleep(100);
    ok((await cell('A3')) === 'done' && (await txt('pstatus')).includes('Done: 1 of 6'), 'picker shows A3 done');

    // Pass B on song 1.
    await p.click('#go-B1'); await sleep(100);
    ok((await txt('title')) === 'Pass B, two feelings: Instant Crush (Daft Punk)', 'pass B title');
    ok((await txt('sub')) === 'How the music sounds, not whether you like it. Both can be high at once.', 'pass B wording line');
    const pw = (await box('pad')).w; ok(Math.abs(pw - 520) < 1, `pad 520 px (${pw})`);
    const labs = await p.$eval('#wrapB', e => e.textContent.toLowerCase());
    ok(!/excited|tense|sad|calm|pleasant/.test(labs) && labs.includes('light / bright') && labs.includes('heavy / dark'), 'pass B axis labels, no corner words');
    ok(near(await numsB(), [0, 0]), 'pad starts at 0, 0');
    const g0 = await rgb('pad'); ok(g0[0] === g0[1] && g0[1] === g0[2], `tint neutral grey at 0, 0 (${g0})`);
    await p.click('#start'); await sleep(150);
    await padTo(1, 0); const gL = await rgb('pad');
    await padTo(0, 1); const gH = await rgb('pad');
    await padTo(1, 1); const gLH = await rgb('pad');
    const sum = x => x[0] + x[1] + x[2], dist = (x, y) => Math.max(...x.map((v, i) => Math.abs(v - y[i])));
    ok(gL[0] > gL[2] && sum(gL) > sum(g0), `light: warmer and brighter (${gL})`);
    ok(gH[2] > gH[0] && sum(gH) < sum(g0), `heavy: deeper and darker (${gH})`);
    ok(dist(gLH, gL) > 40 && dist(gLH, gH) > 40 && dist(gLH, g0) > 25, `both high: a third tint (${gLH})`);
    await padTo(0.62, 0.4); ok(near(await numsB(), [0.62, 0.4]), 'numbers "light 0.62 / heavy 0.40" follow the pointer');
    await p.keyboard.press('ArrowRight'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown');
    ok(near(await numsB(), [0.67, 0.3]), 'arrow keys nudge by 0.05 on both axes');
    ok((await ev(() => trail.length)) > 3 && (await ev(() => trail.every(q => performance.now() - q.ms < 3000))), 'trail of the last 3 s');
    await p.keyboard.press('Space'); ok((await ev(() => take.taps.length)) === 0, 'no taps in pass B');
    await sleep(900);
    await p.reload(); await sleep(400);
    s = await stored();
    ok(s.takes.length === 2 && s.takes[0].status === 'done' && s.takes[1].status === 'interrupted' && s.takes[1].reachedT > 0.5 && s.takes[1].samples.length > 5,
      `reload mid-song: take kept as interrupted (reached ${s.takes[1].reachedT} s), A3 still done`);
    ok((await cell('B1')) === 'not recorded' && (await cell('A3')) === 'done', 'picker after reload');
    await p.click('#go-B1'); await sleep(100);
    ok((await txt('status')).includes('starts again'), 'restart shown');

    // Download, clear, load.
    await p.click('#download'); await sleep(700);
    const dl = JSON.parse(fs.readFileSync(T + '/dl/dial2.json'));
    ok(JSON.stringify(dl) === JSON.stringify(s), 'download equals the saved state');
    ok(dl.version === 2 && dl.rate === 10 && dl.passes.A.axes.energy && dl.passes.B.axes.light && dl.passes.B.axes.heavy && dl.passes.A.taps, 'file states version and axes');
    await ev(k => localStorage.removeItem(k), STORE); await p.reload(); await sleep(300);
    ok((await cell('A3')) === 'not recorded', 'cleared: nothing done');
    await (await p.$('#load')).uploadFile(T + '/dl/dial2.json'); await sleep(400);
    ok((await cell('A3')) === 'done' && (await stored()).takes.length === 2, 'load resumes from the file');
    fs.unlinkSync(T + '/dl/dial2.json');

    // B1 to the end.
    await p.click('#go-B1'); await sleep(100); await p.click('#start'); await sleep(200);
    await padTo(0.3, 0.9); await waitIdle();
    s = await stored(); const B = s.takes[2];
    ok(B.status === 'done' && B.pass === 'B' && B.samples.every(q => q.length === 3) && B.samples.at(-1)[1] === 0.3 && B.samples.at(-1)[2] === 0.9, 'B take: [t, light, heavy]');
    ok(B.samples.length === Math.floor(B.duration * 10 + 1e-9) + 1, `B: one sample per 0.1 s (${B.samples.length})`);
    await p.click('#back'); await sleep(100);

    // Redo A3: two clicks, the discarded take kept.
    await p.click('#redo-A3'); await sleep(100);
    ok((await txt('redo-A3')).startsWith('Really discard') && (await cell('A3')) === 'done', 'first click only asks');
    await p.click('#redo-A3'); await sleep(100);
    s = await stored();
    ok(s.takes[0].status === 'discarded' && s.takes[0].discardedAt && s.takes[0].samples.length === A.samples.length && s.takes[0].taps.length === 1, 'discarded take kept with its samples and taps');
    ok((await txt('title')).startsWith('Pass A, energy: Presence') && !(await hidden('start')), 'redo opens A3 ready to start');
    await p.click('#start'); await sleep(150); await slide(0.5); await waitIdle();
    await p.click('#back'); await sleep(100);
    ok((await cell('A3')) === 'done' && (await cell('B1')) === 'done' && (await txt('pstatus')).includes('Done: 2 of 6'), 'picker: A3, B1 done');

    await p.click('#download'); await sleep(700);
    const fin = JSON.parse(fs.readFileSync(T + '/dl/dial2.json'));
    const st = fin.takes.map(x => `${x.pass}${x.song[4]}:${x.status}`).join(' ');
    ok(st === 'A3:discarded B1:interrupted B1:done A3:done', `final download keeps every take (${st})`);
    const paths = [...new Set(reqs)].sort().join(' ');
    ok(paths === '/dial.html /song1.m4a /song3.m4a', `only the page and the songs requested (${paths})`);
  } finally { await b.close(); }
})().catch(e => { console.error(e.message); process.exit(1); });
