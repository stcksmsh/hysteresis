'use strict';
// node record_ensemble.cjs PREVIEW.html AUDIO OUT.mp4 [seconds]
// A whole song (or the first `seconds`) of an ensemble_preview page, drawn frame by frame (no real time), 1920x1080 / 30 fps H.264, the original audio
// stream copied unchanged. Same drawing hook as the music-arm recorder (window.__ENSEMBLE_PREVIEW__.draw(score_seconds)); the canvas is scaled to fill 1080p.
// HYST_TEMPO_MAP=file.json ({map:[[score s, audio s],...]}) for a song planned on a steady grid.
const fs = require("node:fs"), { spawn, execFileSync } = require("node:child_process");
const puppeteer = require("/secondary/Programming/Github/Hysteresis/node_modules/puppeteer-core");
const [source, audio, output, secondsArg] = process.argv.slice(2);
if (!source || !audio || !output) throw Error("usage: PREVIEW.html AUDIO OUT.mp4 [seconds]");
const fps = 30;
const total = Number(execFileSync("/usr/bin/ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", audio]).toString());
const duration = secondsArg ? Math.min(total, Number(secondsArg)) : total;
const tempo = process.env.HYST_TEMPO_MAP ? JSON.parse(fs.readFileSync(process.env.HYST_TEMPO_MAP)).map : null;
const scoreAt = (t) => { if (!tempo) return t; let i = 1; while (i < tempo.length - 1 && tempo[i][1] < t) i++; const [s0, r0] = tempo[i - 1], [s1, r1] = tempo[i]; return s0 + (t - r0) * (s1 - s0) / (r1 - r0); };
(async () => {
  const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox", "--mute-audio", "--disable-gpu"] });
  let enc;
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.goto("file://" + source, { waitUntil: "load" });
    await page.waitForFunction(() => window.__ENSEMBLE_PREVIEW__);
    await page.evaluate(() => {
      const o = document.createElement("canvas"); o.width = 1920; o.height = 1080; const g = o.getContext("2d");
      window.__frame = (t) => { window.__ENSEMBLE_PREVIEW__.draw(t); const c = document.querySelector("canvas#ensemble"); g.drawImage(c, 0, 0, 1920, 1080); return o.toDataURL("image/jpeg", 0.9); };
    });
    const frames = Math.ceil(duration * fps);
    const whole = !secondsArg || duration >= total;
    enc = spawn("/usr/bin/ffmpeg", ["-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", String(fps), "-i", "-", "-i", audio, "-map", "0:v", "-map", "1:a",
      "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", whole ? "copy" : "aac", "-t", String(duration), "-movflags", "+faststart", output], { stdio: ["pipe", "ignore", "pipe"] });
    let err = ""; enc.stderr.on("data", (b) => { err += b; });
    const done = new Promise((res, rej) => { enc.on("error", rej); enc.on("close", (c) => c === 0 ? res() : rej(Error(err.slice(-2000)))); });
    for (let i = 0; i < frames; i++) {
      const d = await page.evaluate((t) => window.__frame(t), scoreAt(i / fps));
      if (!enc.stdin.write(Buffer.from(d.split(",")[1], "base64"))) await new Promise((r) => enc.stdin.once("drain", r));
      if (i % 1000 === 0) console.log(`frame ${i}/${frames}`);
    }
    enc.stdin.end(); await done;
    console.log(JSON.stringify({ output, frames, fps, duration }));
  } finally { if (enc && enc.exitCode === null) enc.kill(); await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
