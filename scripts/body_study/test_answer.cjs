// test_answer.cjs DIR [URL]: headless check of answer.html (addendum 7) on dummy clips.
// DIR holds answer.html, test/tNN-{a,b,c}.mp4 (3 s each) and an empty dl/; made by
// test_answer.sh. Never run on the real clips.
const puppeteer = require('/home/stcksmsh/Programming/Github/Hysteresis/node_modules/puppeteer-core');
const fs = require('fs'), T = process.argv[2];
const ok = (c, m) => { if (!c) throw Error('FAIL: ' + m); console.log('ok', m); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const b = await puppeteer.launch({ executablePath: '/usr/bin/google-chrome', headless: true, args: ['--no-sandbox', '--autoplay-policy=no-user-gesture-required'] });
  try {
    const p = await b.newPage(); await p.setViewport({ width: 1366, height: 768 });
    const reqs = []; p.on('request', r => reqs.push(r.url()));
    p.on('dialog', d => { throw Error('dialog opened: ' + d.message()); });
    const cdp = await p.createCDPSession();
    await cdp.send('Browser.setDownloadBehavior', { behavior: 'allow', downloadPath: T + '/dl' });
    const url = process.argv[3] || ('file://' + T + '/answer.html');
    await p.goto(url);
    const ev = f => p.evaluate(f), $txt = id => p.$eval('#' + id, e => e.textContent);
    const hidden = id => p.$eval('#' + id, e => e.hidden);
    const stored = () => ev(() => JSON.parse(localStorage.getItem('hyst-bodystudy-answers-v1') || 'null'));

    const fit = await ev(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
      bottom: document.querySelector('#first').getBoundingClientRect().bottom, vw: document.querySelector('.screen').getBoundingClientRect().width }));
    ok(fit.sw <= fit.cw, `no horizontal scroll (${fit.sw} <= ${fit.cw})`);
    ok(fit.bottom <= 768, `controls on screen at 768 px high (bottom ${fit.bottom.toFixed(0)}, video ${fit.vw.toFixed(0)} px wide)`);
    ok((await $txt('progress')) === '1 / 24', 'progress 1 / 24');

    // First pass with checks: letters in order, alone, no seek, pause counted.
    async function firstPass(check) {
      await p.click('#start');
      const seq = [];
      let triedSeek = false, paused = false;
      for (;;) {
        const s = await ev(() => ({ l: document.getElementById('letter').textContent, h: document.getElementById('v').hidden,
          c: document.getElementById('v').controls, t: document.getElementById('v').currentTime,
          count: !document.getElementById('count').hidden, src: document.getElementById('v').getAttribute('src') || '' }));
        if (s.count) break;
        const tag = s.h ? '-' : s.l;
        if (seq[seq.length - 1] !== tag) seq.push(tag);
        if (!s.h && check) {
          if (s.c) throw Error('FAIL: controls shown in first pass');
          if (s.l === 'A' && s.t > 1.2 && !triedSeek) {
            triedSeek = true;
            await ev(() => { document.getElementById('v').currentTime = 0.05; });
            await sleep(300);
            const t = await ev(() => document.getElementById('v').currentTime);
            ok(t > 1.0, `seek back refused in first pass (time ${t.toFixed(2)})`);
            await ev(() => { document.getElementById('v').currentTime = 2.9; });
            await sleep(150);
            const t2 = await ev(() => document.getElementById('v').currentTime);
            ok(t2 < 2.5, `seek forward refused in first pass (time ${t2.toFixed(2)})`);
          }
          if (s.l === 'B' && s.t > 0.5 && !paused) {
            paused = true;
            await p.click('#pause'); await sleep(400);
            const t1 = await ev(() => document.getElementById('v').currentTime); await sleep(400);
            const t2 = await ev(() => document.getElementById('v').currentTime);
            ok(t1 === t2, 'pause holds the clip');
            await p.click('#pause');
          }
        }
        await sleep(80);
      }
      return seq.filter(x => x !== '' && x !== undefined).join('');
    }
    const seq = await firstPass(true);
    ok(seq.replace(/^-/, '') === 'A-B-C-' || seq.replace(/^-/, '') === 'A-B-C', `A, black, B, black, C in order (${seq})`);
    // a replay of C in the first pass is not offered: the video is gone
    ok(await ev(() => document.getElementById('v').hidden), 'no clip on screen after C');
    ok(await hidden('after'), 'replays locked before the counted answer');

    // Counted answer, final and saved.
    await p.click('.pick[data-k="B"]');
    ok(!(await hidden('after')) && (await hidden('count')), 'counted answer moves to replays');
    let st = await stored();
    ok(st.pending && st.pending.counted === 'B' && st.pending.pausesFirstPass === 1, 'counted answer B and 1 pause saved');
    await ev(() => document.querySelector('.pick[data-k="C"]').click());
    ok((await stored()).pending.counted === 'B', 'counted answer cannot change');
    await p.reload(); await sleep(300);
    ok(!(await hidden('after')) && (await $txt('counted')).includes('B'), 'after reload: still counted B, replays shown');
    ok(await hidden('count') && await hidden('first'), 'after reload: no way back to the first pass');

    // Replays with seek.
    await p.click('.replay[data-k="A"]'); await sleep(300);
    ok(await ev(() => document.getElementById('v').controls), 'replay has controls');
    await ev(() => { const v = document.getElementById('v'); v.pause(); v.currentTime = 2.0; }); await sleep(200);
    ok(Math.abs(await ev(() => document.getElementById('v').currentTime) - 2.0) < 0.1, 'replay seeks');
    await ev(() => document.getElementById('v').play()); await sleep(1500);
    await ev(() => document.getElementById('v').play()); await sleep(200);
    await p.click('.replay[data-k="C"]'); await sleep(200);
    await p.click('.second[data-k="C"]'); await p.type('#note', 'slow and low');
    await p.click('#next');
    ok((await $txt('progress')) === '2 / 24', 'next triplet 2 / 24');
    st = await stored();
    const r0 = st.answers[0];
    ok(r0.counted === 'B' && r0.second === 'C' && r0.text === 'slow and low', 'record: counted, second, text');
    ok(r0.replays.A === 2 && r0.replays.C === 1 && r0.replays.B === 0, `record: replays ${JSON.stringify(r0.replays)}`);
    ok(r0.timeToCountedS > 9 && r0.totalS >= r0.timeToCountedS && r0.pausesFirstPass === 1, `record: times ${r0.timeToCountedS.toFixed(1)} / ${r0.totalS.toFixed(1)} s`);

    // A first pass cut off by a reload restarts from A, counts kept.
    await p.click('#start'); await sleep(1200);
    await p.reload(); await sleep(300);
    ok((await $txt('progress')) === '2 / 24' && !(await hidden('first')), 'reload mid first pass: restarts triplet 2');
    await firstPass(false);
    await p.click('.pick[data-k="A"]'); await p.click('#next');
    st = await stored();
    ok(st.answers[1].firstPassStarts === 2 && st.answers[1].counted === 'A' && st.answers[1].second === null, 'record: 2 first-pass starts, no second answer');

    // Download at any point, then resume from the file.
    await p.click('#download'); await sleep(800);
    const dl = JSON.parse(fs.readFileSync(T + '/dl/answers.json'));
    ok(dl.answers.length === 2 && dl.finished === false, 'download mid test: 2 answers');
    await ev(() => localStorage.clear()); await p.reload(); await sleep(300);
    ok((await $txt('progress')) === '1 / 24', 'cleared storage starts at 1 / 24');
    const input = await p.$('#load'); await input.uploadFile(T + '/dl/answers.json'); await sleep(500);
    ok((await $txt('progress')) === '3 / 24', 'loaded file resumes at 3 / 24');
    fs.unlinkSync(T + '/dl/answers.json');

    // Last triplet ends the test; final download.
    await ev(() => { const s = JSON.parse(localStorage.getItem('hyst-bodystudy-answers-v1'));
      while (s.answers.length < 23) s.answers.push({ ...s.answers[0], shown: s.answers.length + 1 });
      localStorage.setItem('hyst-bodystudy-answers-v1', JSON.stringify(s)); });
    await p.reload(); await sleep(300);
    ok((await $txt('progress')) === '24 / 24', 'progress 24 / 24');
    await firstPass(false); await p.click('.pick[data-k="C"]'); await p.click('#next');
    ok(!(await hidden('done')), 'done after 24');
    await p.click('#download2'); await sleep(800);
    const fin = JSON.parse(fs.readFileSync(T + '/dl/answers.json'));
    ok(fin.finished === true && fin.answers.length === 24 && fin.answers[23].counted === 'C', 'final download: 24 answers');

    ok(!reqs.some(u => /key/i.test(u)), 'key.json never requested');
    const other = reqs.filter(u => !u.startsWith('data:') && !u.endsWith('/favicon.ico') && !u.endsWith('answer.html') && !/\/test\/t\d\d-[abc]\.mp4$/.test(u));
    ok(other.length === 0, 'only the page and single clips requested ' + JSON.stringify(other));
    console.log('answer.html checks pass');
  } finally { await b.close(); }
})().catch(e => { console.error(e.message || e); process.exit(1); });
