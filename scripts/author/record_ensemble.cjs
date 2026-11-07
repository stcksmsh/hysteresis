'use strict';
// node record_ensemble.cjs PREVIEW.html AUDIO OUT.mp4 [START_S [DURATION_S]]
// An ensemble_preview page (one arm) drawn frame by frame (no real time), 30 fps H.264, with the song's audio for the same window.
// Default: the whole song at 1920x1080, original audio stream copied unchanged. A window re-encodes its audio (aac).
// HYST_FAST=1: the page's own 1280x720 canvas (no upscale), x264 veryfast crf 23. HYST_TEMPO_MAP=file.json ({map:[[score s, audio s],...]}) for a
// song planned on a steady grid. HYST_JPEG=q (0..1, default 0.9) sets the frame transfer quality.
const fs = require("node:fs"), { spawn, execFileSync } = require("node:child_process");
const puppeteer = require("/secondary/Programming/Github/Hysteresis/node_modules/puppeteer-core");
const [source, audio, output, startArg, durArg] = process.argv.slice(2);
if (!source || !audio || !output) throw Error("usage: PREVIEW.html AUDIO OUT.mp4 [START_S [DURATION_S]]");
const fps = 30, fast = process.env.HYST_FAST === "1", q = Number(process.env.HYST_JPEG || (fast ? 0.8 : 0.9));
const [W, H] = fast ? [1280, 720] : [1920, 1080];
const total = Number(execFileSync("/usr/bin/ffprobe", ["-v", "error", "-show_entries", "format=duration", "-of", "default=nokey=1:noprint_wrappers=1", audio]).toString());
const start = Number(startArg || 0);
if (!(start >= 0 && start < total)) throw Error("START_S must be inside the song");
const duration = Math.min(total - start, durArg ? Number(durArg) : total - start);
if (!(duration > 0)) throw Error("DURATION_S must be positive");
const whole = start === 0 && duration >= total - 1e-6;
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
    await page.evaluate((W, H, q) => {
      const c = document.querySelector("canvas#ensemble");
      let o = c, g = null;
      if (c.width !== W || c.height !== H) { o = document.createElement("canvas"); o.width = W; o.height = H; g = o.getContext("2d"); }
      window.__frame = (t) => { window.__ENSEMBLE_PREVIEW__.draw(t); if (g) g.drawImage(c, 0, 0, W, H); return o.toDataURL("image/jpeg", q); };
    }, W, H, q);
    const frames = Math.ceil(duration * fps);
    enc = spawn("/usr/bin/ffmpeg", ["-y", "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", String(fps), "-i", "-", "-ss", String(start), "-t", String(duration), "-i", audio,
      "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", fast ? "veryfast" : "medium", "-crf", fast ? "23" : "18", "-pix_fmt", "yuv420p",
      "-c:a", whole ? "copy" : "aac", "-t", String(duration), "-movflags", "+faststart", output], { stdio: ["pipe", "ignore", "pipe"] });
    let err = ""; enc.stderr.on("data", (b) => { err += b; });
    const done = new Promise((res, rej) => { enc.on("error", rej); enc.on("close", (c) => c === 0 ? res() : rej(Error(err.slice(-2000)))); });
    for (let i = 0; i < frames; i++) {
      const d = await page.evaluate((t) => window.__frame(t), scoreAt(start + i / fps));
      if (!enc.stdin.write(Buffer.from(d.split(",")[1], "base64"))) await new Promise((r) => enc.stdin.once("drain", r));
      if (i % 1000 === 0 && frames > 1000) console.log(`frame ${i}/${frames}`);
    }
    enc.stdin.end(); await done;
    console.log(JSON.stringify({ output, frames, fps, start, duration, width: W, height: H }));
  } finally { if (enc && enc.exitCode === null) enc.kill(); await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
