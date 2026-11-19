import "./style.css";
import { init } from "sinteza-viz";
// Resolved and copied by this site's own build (the package's
// import.meta.url default breaks once a bundler relocates its code).
import renderWorkerUrl from "sinteza-viz/dist/render-worker.js?url";
import workletUrl from "sinteza-viz/dist/worklets/feature-worklet.js?url";

const BASE = import.meta.env.BASE_URL;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const $ = (s) => document.querySelector(s);
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

const TRACKS = [
  { slug: "hysteresis", title: "Hysteresis", accent: [0.686, 0.205, 34] },
  { slug: "sigsegv", title: "SIGSEGV", accent: [0.68, 0.22, 25] },
  { slug: "0xc000021a", title: "0xC000021A", accent: [0.65, 0.22, 15] },
  { slug: "sampling-drift", title: "Sampling Drift", accent: [0.75, 0.13, 200] },
  { slug: "triple-pendulum", title: "Triple Pendulum", accent: [0.64, 0.25, 300] },
].map((t) => ({ ...t, embed: `https://soundcloud.com/stcksmsh/${t.slug}`, sidecar: `${BASE}sidecars/${t.slug}.sidecar.json` }));

const transport = (detail) => window.dispatchEvent(new CustomEvent("player:transport", { detail }));

/* ---------- the visualizer ---------- */
let viz = null;
let mode = "sc"; // "sc" | "local"
let actx = null, analyser = null;
const canvas = $("#viz");
function startViz() {
  if (viz) return;
  viz = init(canvas, {
    accent: TRACKS[0].accent,
    tier: "full",
    renderWorkerUrl,
    workletUrl,
    getAudioContext: () => (mode === "local" ? actx : null),
    getAnalyser: () => (mode === "local" ? analyser : null),
  });
  $("#viz-poster").hidden = true;
  $("#rm-note").hidden = true;
  addEventListener("resize", () => viz.resize());
}
if (reduced) {
  $("#viz-poster").hidden = false;
  $("#rm-note").hidden = false;
  $("#viz-start").addEventListener("click", startViz);
} else startViz();

$("#clear-btn").addEventListener("click", (e) => {
  const on = document.body.classList.toggle("clear");
  e.currentTarget.setAttribute("aria-pressed", String(on));
  e.currentTarget.textContent = on ? "Show the text" : "Hide the text";
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && document.body.classList.contains("clear")) $("#clear-btn").click();
});

document.querySelectorAll("input[name=tier]").forEach((r) => r.addEventListener("change", () => viz?.setTier(r.value)));

/* ---------- SoundCloud transport ---------- */
const ui = { play: $("#play-btn"), pos: $("#t-pos"), dur: $("#t-dur"), now: $("#now"), list: $("#tracks") };
let widget = null, current = null, playing = false, durMs = 0, posMs = 0;

ui.list.innerHTML = TRACKS.map((t, i) => `<li><button type="button" data-i="${i}" aria-pressed="false">
  <span class="sw" style="--c: oklch(${t.accent[0]} ${t.accent[1]} ${t.accent[2]})"></span>${t.title}</button></li>`).join("");

function loadApi() {
  return new Promise((res, rej) => {
    if (window.SC?.Widget) return res();
    const s = document.createElement("script");
    s.src = "https://w.soundcloud.com/player/api.js";
    s.onload = () => res();
    s.onerror = rej;
    document.head.appendChild(s);
  });
}
function fetchDuration(attempt = 0) {
  widget?.getDuration((ms) => {
    if (ms > 0) { durMs = ms; ui.dur.textContent = mmss(ms / 1000); return; }
    if (attempt < 6) setTimeout(() => fetchDuration(attempt + 1), 250);
  });
}
loadApi().then(() => {
  const SC = window.SC;
  widget = SC.Widget($("#sc"));
  widget.bind(SC.Widget.Events.READY, () => { ui.play.disabled = false; fetchDuration(); });
  widget.bind(SC.Widget.Events.PLAY, () => { playing = true; syncPlay(); if (mode === "sc") transport({ type: "play" }); fetchDuration(); });
  widget.bind(SC.Widget.Events.PAUSE, () => { playing = false; syncPlay(); if (mode === "sc") transport({ type: "pause" }); });
  widget.bind(SC.Widget.Events.FINISH, () => {
    playing = false; syncPlay(); transport({ type: "pause" });
    pick((TRACKS.indexOf(current) + 1) % TRACKS.length);
  });
  widget.bind(SC.Widget.Events.PLAY_PROGRESS, (e) => {
    posMs = e.currentPosition;
    ui.pos.textContent = mmss(posMs / 1000);
    if (mode === "sc") transport({ type: "position", positionSec: posMs / 1000 });
    strip.playhead(posMs / 1000);
  });
}).catch(() => { ui.now.textContent = "SoundCloud didn't load. You can still bring your own file."; });

function syncPlay() {
  ui.play.textContent = playing ? "❚❚" : "▶";
  ui.play.setAttribute("aria-label", playing ? "Pause" : "Play");
}

function pick(i, autoPlay = true) {
  const t = TRACKS[i];
  if (!widget) return;
  goSc();
  current = t;
  durMs = 0; posMs = 0;
  ui.pos.textContent = "0:00"; ui.dur.textContent = "…";
  ui.now.textContent = t.title;
  ui.list.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", String(+b.dataset.i === i)));
  transport({ type: "trackchange", track: { slug: t.slug, title: t.title, accent: t.accent, envelope: t.sidecar } });
  viz?.setAccent(t.accent);
  widget.load(t.embed, { auto_play: autoPlay, hide_related: true, show_comments: false, show_reposts: false, show_teaser: false, visual: false, callback: () => fetchDuration() });
  strip.show(t);
}
ui.list.addEventListener("click", (e) => {
  const b = e.target.closest("button[data-i]");
  if (b) pick(+b.dataset.i);
});
ui.play.addEventListener("click", () => {
  if (!current) return pick(0);
  if (mode !== "sc") goSc();
  widget.toggle();
});

/* ---------- your own file: live analysis ---------- */
const audio = $("#audio");
let srcNode = null;
function goSc() {
  if (mode === "sc") return;
  audio.pause();
  mode = "sc";
}
$("#file").addEventListener("change", async (e) => {
  const f = e.target.files?.[0];
  if (!f) return;
  widget?.pause();
  if (!actx) {
    actx = new AudioContext();
    analyser = actx.createAnalyser();
    analyser.fftSize = 2048;
    srcNode = actx.createMediaElementSource(audio);
    srcNode.connect(analyser);
    analyser.connect(actx.destination);
  }
  await actx.resume();
  mode = "local";
  if (audio.src) URL.revokeObjectURL(audio.src);
  audio.src = URL.createObjectURL(f);
  audio.hidden = false;
  current = null;
  ui.list.querySelectorAll("button").forEach((b) => b.setAttribute("aria-pressed", "false"));
  ui.now.textContent = `${f.name} (live analysis)`;
  transport({ type: "trackchange", track: { slug: "local", title: f.name } });
  strip.show(null);
  startViz();
  audio.play().catch(() => {});
});
audio.addEventListener("play", () => mode === "local" && transport({ type: "play" }));
audio.addEventListener("pause", () => mode === "local" && transport({ type: "pause" }));
audio.addEventListener("timeupdate", () => mode === "local" && transport({ type: "position", positionSec: audio.currentTime }));
audio.addEventListener("seeked", () => mode === "local" && transport({ type: "seek", positionSec: audio.currentTime }));

/* ---------- sidecar strip ---------- */
const strip = (() => {
  const cv = $("#strip");
  const meta = $("#sc-meta");
  const cache = new Map();
  let data = null, track = null, head = -1;
  const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
  const get = async (t) => {
    if (!cache.has(t.slug)) cache.set(t.slug, fetch(t.sidecar).then((r) => r.json()));
    return cache.get(t.slug);
  };
  const draw = () => {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const W = cv.clientWidth, H = 220;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    if (!data) {
      g.fillStyle = "#ffffff80";
      g.font = "13px ui-monospace, monospace";
      g.fillText(track === null ? "Your own file has no sidecar: everything is detected live." : "Loading…", 12, 24);
      return;
    }
    const D = data.duration;
    const x = (t) => (t / D) * W;
    // sections
    for (const s of data.sections) {
      g.fillStyle = s.kind === "break" ? css("--k-break") : css("--k-build");
      g.fillRect(x(s.start), 0, Math.max(1, x(s.end) - x(s.start)), H - 18);
    }
    // breaks from events
    let bs = null;
    for (const e of data.events) {
      if (e.type === "breakStart") bs = e.t;
      if (e.type === "breakEnd" && bs != null) { g.fillStyle = css("--k-break"); g.fillRect(x(bs), 0, x(e.t) - x(bs), H - 18); bs = null; }
    }
    if (bs != null) { g.fillStyle = css("--k-break"); g.fillRect(x(bs), 0, x(D) - x(bs), H - 18); }
    const plot = (arr, color, lw, scale = 1, fill = false) => {
      // average per pixel column (envelopes are 20 fps, far denser than the strip)
      const n = arr.length, cols = Math.max(2, Math.floor(W / 2));
      const base = H - 22;
      g.beginPath();
      for (let c = 0; c < cols; c++) {
        const a = Math.floor((c / cols) * n), b = Math.max(a + 1, Math.floor(((c + 1) / cols) * n));
        let m = 0;
        for (let i = a; i < b && i < n; i++) m += arr[i];
        m /= b - a;
        const px = (c / (cols - 1)) * x(n / data.envelopeRate), py = base - m * scale * (H - 40);
        c ? g.lineTo(px, py) : g.moveTo(px, py);
      }
      if (fill) { g.lineTo(x(n / data.envelopeRate), base); g.lineTo(0, base); g.fillStyle = color; g.fill(); }
      else { g.strokeStyle = color; g.lineWidth = lw; g.lineJoin = "round"; g.stroke(); }
    };
    plot(data.energyEnvelope, "rgb(255 255 255 / 0.12)", 0, 1, true);
    plot(data.bandEnvelope.sub, css("--k-sub"), 1.6, 0.9);
    plot(data.bandEnvelope.presence, css("--k-presence"), 1.6, 0.9);
    plot(data.energyEnvelope, css("--k-energy"), 2);
    // downbeats
    g.fillStyle = css("--k-beat");
    for (const e of data.events) if (e.type === "downbeat") g.fillRect(x(e.t), H - 14, 1, 8);
    // drops
    for (const e of data.events) if (e.type === "drop") {
      g.fillStyle = css("--k-drop");
      g.fillRect(x(e.t) - 1, 0, 3, H - 18);
      g.beginPath(); g.moveTo(x(e.t) - 6, 0); g.lineTo(x(e.t) + 6, 0); g.lineTo(x(e.t), 9); g.fill();
    }
    bg = document.createElement("canvas");
    bg.width = cv.width; bg.height = cv.height;
    bg.getContext("2d").drawImage(cv, 0, 0);
    paintHead();
  };
  let bg = null, queued = false;
  const paintHead = () => {
    queued = false;
    if (!bg || !data) return;
    const g = cv.getContext("2d");
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.clearRect(0, 0, cv.width, cv.height);
    g.drawImage(bg, 0, 0);
    if (head >= 0) {
      const dpr = cv.width / cv.clientWidth;
      g.fillStyle = "#fff";
      g.fillRect(((head / data.duration) * cv.clientWidth - 1) * dpr, 0, 2 * dpr, cv.height);
    }
  };
  const show = async (t) => {
    track = t; data = null; head = -1; bg = null;
    draw();
    if (!t) { meta.innerHTML = ""; return; }
    const d = await get(t);
    if (track !== t) return;
    data = d;
    const n = (k) => d.events.filter((e) => e.type === k).length;
    meta.innerHTML = [
      ["track", t.title], ["duration", mmss(d.duration)], ["tempo", `${d.tempo.toFixed(1)} bpm`], ["beats", d.beats.length],
      ["sections", d.sections.length], ["drops", n("drop")], ["breaks", n("breakStart")], ["onsets", d.onsets.length],
    ].map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("");
    meta.setAttribute("role", "list");
    draw();
  };
  cv.addEventListener("click", (e) => {
    if (!data || !track) return;
    const r = cv.getBoundingClientRect();
    const t = ((e.clientX - r.left) / r.width) * data.duration;
    if (current !== track) { pick(TRACKS.indexOf(track)); return; }
    widget?.seekTo(t * 1000);
    transport({ type: "seek", positionSec: t });
    if (!playing) widget?.play();
  });
  let lastW = 0;
  new ResizeObserver(() => { if (cv.clientWidth !== lastW) { lastW = cv.clientWidth; draw(); } }).observe(cv);
  return { show, playhead: (t) => { head = t; if (data && !queued) { queued = true; requestAnimationFrame(paintHead); } } };
})();
strip.show(TRACKS[0]);

/* ---------- memory illustration ---------- */
{
  const cv = $("#mem");
  const range = $("#mem-r"), out = $("#mem-o");
  const T = 40, RATE = 50;
  // a toy arrangement: groove, a single loud hit, a long build, the drop, a short break, back in
  const input = Array.from({ length: T * RATE }, (_, i) => {
    const t = i / RATE;
    const pulse = 0.5 + 0.5 * Math.cos(2 * Math.PI * 2 * t); // 120 bpm
    let lvl = 0.3;
    if (t > 4 && t < 4.4) lvl = 0.95; // one hit
    if (t >= 10 && t < 20) lvl = 0.3 + 0.6 * ((t - 10) / 10); // build
    if (t >= 20 && t < 28) lvl = 0.92; // drop
    if (t >= 28 && t < 31) lvl = 0.04; // break
    if (t >= 31) lvl = 0.55;
    return Math.max(0, Math.min(1, lvl * (0.75 + 0.25 * pulse)));
  });
  const follow = (tau, tauDown = tau) => {
    let s = 0;
    return input.map((v) => {
      const k = v > s ? 1 / (tau * RATE) : 1 / (tauDown * RATE);
      s += (v - s) * Math.min(1, k);
      return s;
    });
  };
  let fast = follow(0.05, 0.15), slow = [];
  const compute = () => { slow = follow(+range.value, +range.value * 2.5); out.textContent = `${(+range.value).toFixed(1)} s`; };
  let t0 = performance.now();
  const draw = (now = performance.now()) => {
    const dpr = Math.min(2, devicePixelRatio || 1);
    const W = cv.clientWidth, H = 240;
    if (cv.width !== Math.round(W * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
    const g = cv.getContext("2d");
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, W, H);
    const lab = [[0, "groove"], [4, "one hit"], [10, "build"], [20, "drop"], [28, "break"], [31, "back in"]];
    g.font = "11px ui-monospace, monospace";
    g.fillStyle = "#ffffff70";
    let lastEnd = -1;
    for (const [t, s] of lab) {
      const px = (t / T) * W;
      g.fillRect(px, 0, 1, H);
      if (px + 4 > lastEnd + 4) { g.fillText(s, px + 4, 13); lastEnd = px + 4 + g.measureText(s).width; }
    }
    const line = (arr, color, lw, fill) => {
      g.beginPath();
      arr.forEach((v, i) => { const px = (i / arr.length) * W, py = H - 8 - v * (H - 30); i ? g.lineTo(px, py) : g.moveTo(px, py); });
      if (fill) { g.lineTo(W, H - 8); g.lineTo(0, H - 8); g.fillStyle = color; g.fill(); }
      else { g.strokeStyle = color; g.lineWidth = lw; g.stroke(); }
    };
    line(input, "#ffffff1c", 0, true);
    line(fast, "#ffffff99", 1.2);
    line(slow, "oklch(0.75 0.19 34)", 3);
    if (!reduced) {
      const ph = (((now - t0) / 1000) % T) / T;
      const i = Math.floor(ph * input.length);
      const px = ph * W;
      g.fillStyle = "#fff";
      g.fillRect(px, 18, 1, H - 26);
      for (const [arr, r] of [[fast, 3], [slow, 5]]) {
        g.beginPath(); g.arc(px, H - 8 - arr[i] * (H - 30), r, 0, 7); g.fill();
      }
    }
  };
  range.addEventListener("input", () => { compute(); draw(); });
  compute();
  new ResizeObserver(() => draw()).observe(cv);
  if (!reduced) {
    let vis = false;
    new IntersectionObserver(([e]) => (vis = e.isIntersecting)).observe(cv);
    const loop = (now) => { if (vis && !document.hidden) draw(now); requestAnimationFrame(loop); };
    requestAnimationFrame(loop);
  }
}
