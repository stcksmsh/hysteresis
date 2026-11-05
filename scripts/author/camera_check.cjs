// camera_check.cjs PAGE.html [STEP_S]: project every arm point and the hand disc of a one-arm page (every STEP_S, default 0.1 s)
// with the page's own camera and report the share of samples with any part outside the 1280x720 view and the minimum margin (px).
// The camera is the page's script text from "const solo" to "function line(", run as is, so the check cannot drift from the page.
const fs = require('fs'), h = fs.readFileSync(process.argv[2], 'utf8'), step = +(process.argv[3] || 0.1);
const js = h.slice(h.indexOf('<script>') + 8, h.lastIndexOf('</script>'));
const data = JSON.parse(js.match(/const data = (\{[\s\S]*?\});\n\s*const audio/)[1]);
const helpers = js.slice(js.indexOf('// ENSEMBLE_HELPERS_BEGIN'), js.indexOf('// ENSEMBLE_HELPERS_END'));
const cam = js.slice(js.indexOf('const solo='), js.indexOf('function line('));
const { frameAt, project } = new Function('data', helpers + cam + 'return {frameAt,project};')(data);
const r = (data.rig.implement && data.rig.implement.radiusM) || 0.1;
let n = 0, out = 0, min = 1e9, worst = 0;
for (let t = 0; t <= data.duration; t += step) {
  n++; let m = 1e9;
  for (const arm of frameAt(data, t).agents) {
    arm.forEach((p, k) => {
      const [x, y, d] = project(p), pad = k === arm.length - 1 ? 1800 * r / Math.max(d, 0.1) : 0;
      m = Math.min(m, x - pad, 1280 - x - pad, y - pad, 720 - y - pad);
    });
  }
  if (m < 0) out++;
  if (m < min) { min = m; worst = t; }
}
console.log(JSON.stringify({ samples: n, outsideShare: out / n, minMarginPx: +min.toFixed(1), atS: +worst.toFixed(1) }));
