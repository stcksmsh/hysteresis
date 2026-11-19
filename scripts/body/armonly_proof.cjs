'use strict';
// node armonly_proof.cjs PAGE.html T_S OUT.png   (WO55 B, docs/MISMATCH2_RULES.md section 0 item 3)
// Draws one frame of an ensemble_preview page at score time T_S, counts the canvas stroke calls of the look-ahead hint
// (strokeStyle #6f8997 at globalAlpha 0.25) and of the trail (shadowBlur 14, lineCap butt), saves the frame as PNG, prints JSON.
const fs = require("node:fs");
const puppeteer = require("/secondary/Programming/Github/Hysteresis/node_modules/puppeteer-core");
const [page_, tArg, out] = process.argv.slice(2);
(async () => {
  const browser = await puppeteer.launch({ executablePath: "/usr/bin/google-chrome", headless: true, args: ["--no-sandbox", "--mute-audio", "--disable-gpu"] });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1920, height: 1080 });
    await page.goto("file://" + page_, { waitUntil: "load" });
    await page.waitForFunction(() => window.__ENSEMBLE_PREVIEW__);
    const r = await page.evaluate((t) => {
      const P = CanvasRenderingContext2D.prototype, orig = P.stroke, n = { strokes: 0, hint: 0, trail: 0 };
      P.stroke = function (...a) {
        n.strokes++;
        if (this.strokeStyle === "#6f8997" && Math.abs(this.globalAlpha - 0.25) < 1e-6) n.hint++;
        if (this.shadowBlur === 14 && this.lineCap === "butt") n.trail++;
        return orig.apply(this, a);
      };
      window.__ENSEMBLE_PREVIEW__.draw(t);
      P.stroke = orig;
      return { ...n, png: document.querySelector("canvas#ensemble").toDataURL("image/png") };
    }, Number(tArg));
    fs.writeFileSync(out, Buffer.from(r.png.split(",")[1], "base64"));
    delete r.png;
    console.log(JSON.stringify({ page: page_, t: Number(tArg), ...r }));
  } finally { await browser.close(); }
})().catch((e) => { console.error(e); process.exitCode = 1; });
