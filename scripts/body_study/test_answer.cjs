// test_answer.cjs DIR [URL]: headless check of answer.html (addendum 8) on dummy clips.
// DIR holds answer.html, test/{pN,tNN}-{a,b,c}.mp4 (3 s each), test/practice.js with
// odd positions A, B, C, A, and an empty dl/; made by test_answer.sh. Never run on the
// real clips.
const puppeteer = require('/home/stcksmsh/Programming/Github/Hysteresis/node_modules/puppeteer-core');
const fs = require('fs'), T = process.argv[2];
const ok = (c, m) => { if (!c) throw Error('FAIL: ' + m); console.log('ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const STORE = 'hyst-bodystudy-r6-v1';
(async () => {
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const p = await b.newPage(); await p.setViewport({ width: 1366, height: 768 });
    const reqs = []; p.on('request', r => reqs.push(r.url()));
    p.on('dialog', d => { throw Error('dialog opened: ' + d.message()); });
    const cdp = await p.createCDPSession();
    await cdp.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: T + '/dl' });
    const url = process.argv[3] || ('file://' + T + '/answer.html');
    await p.goto(url); await sleep(300);
    const ev = (f, ...a) => p.evaluate(f, ...a), $txt = id => p.$eval('#' + id, e => e.textContent);
    const hidden = id => p.$eval('#' + id, e => e.hidden);
    const stored = () => ev(k => JSON.parse(localStorage.getItem(k) || 'null'), STORE);
    const vid = () => ev(() => { const v = document.getElementById('v');
      return { h: v.hidden, c: v.controls, t: v.currentTime, paused: v.paused, src: v.getAttribute('src') || '', l: document.getElementById('letter').textContent }; });
    const disabled = sel => p.$eval(sel, e => e.disabled);

    const fit = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
      bottom: document.querySelector('#first').getBoundingClientRect().bottom, vw: document.querySelector('.screen').getBoundingClientRect().width }));
    ok(fit.sw <= fit.cw, `no horizontal scroll (${fit.sw} <= ${fit.cw})`);
    ok(fit.bottom <= 768, `controls on screen at 768 px high (bottom ${fit.bottom.toFixed(0)}, video ${fit.vw.toFixed(0)} px wide)`);
    ok((await $txt('progress')) === 'Practice 1 / 4', 'practice first: Practice 1 / 4');

    // Seek attempts on the locked video must be undone.
    async function seekRefused(what) {
      await ev(() => { document.getElementById('v').currentTime = 0.05; }); await sleep(300);
      const t = (await vid()).t;
      ok(t > 0.6, `${what}: seek back refused (time ${t.toFixed(2)})`);
      await ev(() => { document.getElementById('v').currentTime = 2.9; }); await sleep(150);
      const t2 = (await vid()).t;
      ok(t2 < 2.5, `${what}: seek forward refused (time ${t2.toFixed(2)})`);
    }
    // First pass: letters in order, alone, no controls, no seek, pause counted.
    async function firstPass(check, prefix) {
      await p.click('#start');
      const seq = [];
      let triedSeek = false, paused = false;
      for (;;) {
        const s = await vid();
        if (!(await hidden('count'))) break;
        const tag = s.h ? '-' : s.l;
        if (seq[seq.length - 1] !== tag) seq.push(tag);
        if (!s.h) {
          if (s.c) throw Error('FAIL: controls shown in first pass');
          if (!s.src.includes(prefix)) throw Error('FAIL: wrong clip ' + s.src);
        }
        if (!s.h && check) {
          if (s.l === 'A' && s.t > 1.0 && !triedSeek) { triedSeek = true; await seekRefused('first pass'); }
          if (s.l === 'B' && s.t > 0.5 && !paused) {
            paused = true;
            await p.click('#pause'); await sleep(400);
            const t1 = (await vid()).t; await sleep(400);
            ok(t1 === (await vid()).t, 'pause holds the clip');
            await p.click('#pause');
          }
        }
        await sleep(80);
      }
      const order = seq.join('').replace(/^-/, '');
      ok(order === 'A-B-C-' || order === 'A-B-C', `A, black, B, black, C in order (${order})`);
    }
    // A replay before the counted answer: alone, locked, from the start, to its end.
    async function preReplay(k, check) {
      await p.click(`.pre[data-k="${k}"]`); await sleep(250);
      const s = await vid();
      ok(!s.h && !s.c && s.l === k && s.t < 1.0, `replay ${k} before answering: alone, no controls, from the start`);
      ok(await disabled('.pre[data-k="A"]') && await disabled('.pre[data-k="B"]') && await disabled('.pre[data-k="C"]'), 'no other replay while one plays');
      if (check) { await sleep(700); await seekRefused(`replay ${k}`); }
      while (!(await vid()).h) await sleep(100);
    }

    // Practice 1 (odd A): replay cap, then a wrong answer shows odd and pair together.
    await firstPass(true, 'p1-');
    ok(await hidden('after') && await hidden('feedback'), 'nothing after the first pass but replays and the counted answer');
    for (const k of 'ABC') ok(!(await disabled(`.pre[data-k="${k}"]`)), `replay ${k} offered after the first pass`);
    await preReplay('A', true);
    ok(await disabled('.pre[data-k="A"]'), 'replay of A again refused (button)');
    await ev(() => document.querySelector('.pre[data-k="A"]').click()); await sleep(200);
    ok((await vid()).h, 'replay of A again refused (click does nothing)');
    await preReplay('C', false);
    ok(await disabled('.pre[data-k="B"]'), 'third replay refused (button)');
    await ev(() => document.querySelector('.pre[data-k="B"]').click()); await sleep(200);
    ok((await vid()).h, 'third replay refused (click does nothing)');
    let st = await stored();
    ok(JSON.stringify(st.firstPass.replaysBeforeCounted) === '{"A":1,"B":0,"C":1}', 'replays before the counted answer saved per clip');
    await p.reload(); await sleep(400);
    ok(!(await hidden('count')) && await disabled('.pre[data-k="B"]'), 'after reload: back at the counted answer, replay cap kept');
    await p.click('.pick[data-k="B"]'); await sleep(300);
    ok(!(await hidden('feedback')) && (await $txt('verdict')).startsWith('Wrong'), 'practice: wrong answer reported');
    ok(await hidden('after'), 'practice: no second answer or text');
    ok(!(await hidden('pairview')), 'practice wrong: odd and pair side by side');
    const srcs = await ev(() => [document.getElementById('vOdd').getAttribute('src'), document.getElementById('vPair').getAttribute('src')]);
    ok(srcs[0].endsWith('p1-a.mp4') && /p1-[bc]\.mp4$/.test(srcs[1]), `practice wrong: odd clip and one pair clip (${srcs.join(', ')})`);
    for (let n = 0; n < 2; n++) {
      await p.click('#playBoth'); await sleep(700);
      const both = await ev(() => ['vOdd', 'vPair'].map(id => { const x = document.getElementById(id); return { p: x.paused, t: x.currentTime }; }));
      ok(both.every(x => !x.p && x.t > 0.3) && Math.abs(both[0].t - both[1].t) < 0.25, `practice wrong: both play together (play ${n + 1})`);
    }
    await p.click('#nextPractice'); await sleep(300);
    st = await stored();
    ok(st.practice.length === 1 && st.practice[0].correct === false && st.practice[0].pairPlays === 2, 'practice record: wrong, 2 joint plays');
    ok((await $txt('progress')) === 'Practice 2 / 4', 'Practice 2 / 4');

    // Practice 2 (odd B): right answer, no side by side.
    await firstPass(false, 'p2-');
    await p.click('.pick[data-k="B"]'); await sleep(300);
    ok((await $txt('verdict')).startsWith('Right') && await hidden('pairview'), 'practice right: reported, no side by side');
    await p.click('#nextPractice'); await sleep(300);

    // Skip practice 3 and 4 by storage, then scored triplet 1.
    await ev(k => { const s = JSON.parse(localStorage.getItem(k));
      while (s.practice.length < 4) s.practice.push({ ...s.practice[1], shown: `p${s.practice.length + 1}` });
      localStorage.setItem(k, JSON.stringify(s)); }, STORE);
    await p.reload(); await sleep(400);
    ok((await $txt('progress')) === '1 / 32', 'scored after practice: 1 / 32');
    await firstPass(false, 't01-');
    await preReplay('B', false);
    await p.click('.pick[data-k="C"]'); await sleep(200);
    ok(!(await hidden('after')) && await hidden('feedback'), 'scored: no feedback, replays after the counted answer');
    ok(!(await $txt('counted')).includes('Wrong') && !(await $txt('counted')).includes('Right'), 'scored: no right or wrong shown');
    await ev(() => document.querySelector('.pick[data-k="A"]').click());
    ok((await stored()).pending.counted === 'C', 'counted answer cannot change');
    await p.reload(); await sleep(400);
    ok(!(await hidden('after')) && (await $txt('counted')).includes('C'), 'after reload: still counted C');
    ok(await hidden('count') && await hidden('first'), 'after reload: no way back to the first pass');
    await p.click('.replay[data-k="A"]'); await sleep(300);
    ok((await vid()).c, 'replay after the counted answer has controls');
    await ev(() => { const v = document.getElementById('v'); v.pause(); v.currentTime = 2.0; }); await sleep(200);
    ok(Math.abs((await vid()).t - 2.0) < 0.1, 'replay after the counted answer seeks');
    await ev(() => document.getElementById('v').play()); await sleep(1500);
    await ev(() => document.getElementById('v').play()); await sleep(200);
    await p.click('.second[data-k="A"]'); await p.type('#note', 'slow and low');
    await p.click('#next'); await sleep(200);
    ok((await $txt('progress')) === '2 / 32', 'next triplet 2 / 32');
    st = await stored();
    const r0 = st.answers[0];
    ok(r0.shown === 1 && r0.counted === 'C' && r0.second === 'A' && r0.text === 'slow and low', 'record: shown, counted, second, text');
    ok(JSON.stringify(r0.replaysBeforeCounted) === '{"A":0,"B":1,"C":0}', `record: replays before counted ${JSON.stringify(r0.replaysBeforeCounted)}`);
    ok(r0.replays.A === 2 && r0.replays.B === 0 && r0.replays.C === 0, `record: replays after ${JSON.stringify(r0.replays)}`);
    ok(r0.timeToCountedS > 9 && r0.totalS >= r0.timeToCountedS && r0.pausesFirstPass === 0, `record: times ${r0.timeToCountedS.toFixed(1)} / ${r0.totalS.toFixed(1)} s`);

    // A first pass cut off by a reload restarts from A, counts kept.
    await p.click('#start'); await sleep(1200);
    await p.reload(); await sleep(400);
    ok((await $txt('progress')) === '2 / 32' && !(await hidden('first')), 'reload mid first pass: restarts triplet 2');
    await firstPass(false, 't02-');
    await p.click('.pick[data-k="A"]'); await p.click('#next');
    st = await stored();
    ok(st.answers[1].firstPassStarts === 2 && st.answers[1].counted === 'A' && st.answers[1].second === null, 'record: 2 first-pass starts, no second answer');

    // Download at any point, then resume from the file.
    await p.click('#download'); await sleep(800);
    const dl = JSON.parse(fs.readFileSync(T + '/dl/answers.json'));
    ok(dl.answers.length === 2 && dl.practice.length === 4 && dl.finished === false, 'download mid test: 4 practice, 2 answers');
    await ev(() => localStorage.clear()); await p.reload(); await sleep(400);
    ok((await $txt('progress')) === 'Practice 1 / 4', 'cleared storage starts at practice 1');
    const input = await p.$('#load'); await input.uploadFile(T + '/dl/answers.json'); await sleep(500);
    ok((await $txt('progress')) === '3 / 32', 'loaded file resumes at 3 / 32');
    fs.unlinkSync(T + '/dl/answers.json');

    // Last triplet ends the test; final download.
    await ev(k => { const s = JSON.parse(localStorage.getItem(k));
      while (s.answers.length < 31) s.answers.push({ ...s.answers[0], shown: s.answers.length + 1 });
      localStorage.setItem(k, JSON.stringify(s)); }, STORE);
    await p.reload(); await sleep(400);
    ok((await $txt('progress')) === '32 / 32', 'progress 32 / 32');
    await firstPass(false, 't32-'); await p.click('.pick[data-k="C"]'); await p.click('#next');
    ok(!(await hidden('done')), 'done after 32');
    await p.click('#download2'); await sleep(800);
    const fin = JSON.parse(fs.readFileSync(T + '/dl/answers.json'));
    ok(fin.finished === true && fin.answers.length === 32 && fin.answers[31].counted === 'C' && fin.answers[31].shown === 32, 'final download: 32 answers');

    ok(!reqs.some(u => /key/i.test(u)), 'key.json never requested');
    const other = reqs.filter(u => !u.startsWith('data:') && !u.endsWith('/favicon.ico') && !u.endsWith('answer.html')
      && !/\/test\/(t\d\d|p\d)-[abc]\.mp4$/.test(u) && !u.endsWith('/test/practice.js'));
    ok(other.length === 0, 'only the page, practice.js and single clips requested ' + JSON.stringify(other));
    console.log('answer.html checks pass');
  } finally { await b.close(); }
})().catch(e => { console.error(e.message || e); process.exit(1); });
