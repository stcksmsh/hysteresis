// node export_cli.cjs MAPPING.json DATA.json SONG [phrase|beat] > SONG.bodytrack.json
// The page's Export without the page: same author_core.cjs, data from build.py's data.json.
const fs = require("node:fs");
const A = require("./author_core.cjs");

function spans(song, kind) {
  if (kind === "phrase") return song.phrases;
  const b = song.beats, out = [];
  if (b[0] > 0.05) out.push([0, b[0]]);
  for (let i = 0; i + 1 < b.length; i++) out.push([b[i], b[i + 1]]);
  out.push([b[b.length - 1], Math.max(song.duration, b[b.length - 1] + 0.5)]);
  return out;
}

function exportTrack(mapping, song, kind = "phrase") {
  const body = A.computeBody(mapping, A.inputLanes(song, mapping.spike));
  return { bodyTrack: A.bodyTrack(body, spans(song, kind), "authored-state", "authored:" + (mapping.name || "unnamed")) };
}

if (require.main === module) {
  const [mp, dp, name, kind] = process.argv.slice(2);
  const mapping = A.validateMapping(JSON.parse(fs.readFileSync(mp, "utf8")));
  const data = JSON.parse(fs.readFileSync(dp, "utf8"));
  process.stdout.write(JSON.stringify(exportTrack(mapping, data[name], kind)));
}
module.exports = { exportTrack, spans };
