// Many Overlay stills from one bundle, with each still's text measurements (Overlay `measure` mode).
//
//   node scripts/stills.mjs < jobs.json
//   jobs.json: {"publicDir": "<dir>", "jobs": [{"props": "<props.json>", "frame": 36, "out": "<png>", "scale": 0.5}]}
//
// Prints one JSON line per job, in order: {"out", "measure": [{event, texts: [{text, box, size}]}] | null}.
// A job whose props say `"measure": true` logs its measurements from the page; the CLI's `remotion still`
// drops browser logs, which is why this script exists. A failed job prints {"out", "error"} and the
// script exits 1 after the rest.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { publicDir, jobs } = JSON.parse(fs.readFileSync(0, "utf8"));

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.ts"), publicDir, rspack: true });
let failed = false;
for (const job of jobs) {
  const inputProps = JSON.parse(fs.readFileSync(job.props, "utf8"));
  let measure = null;
  try {
    const composition = await selectComposition({ serveUrl, id: "Overlay", inputProps, logLevel: "error" });
    await renderStill({
      serveUrl,
      composition,
      inputProps,
      frame: job.frame,
      output: job.out,
      scale: job.scale ?? 1,
      logLevel: "error",
      onBrowserLog: (log) => {
        if (log.text.startsWith("MEASURE ")) measure = JSON.parse(log.text.slice("MEASURE ".length));
      },
    });
    process.stdout.write(JSON.stringify({ out: job.out, measure }) + "\n");
  } catch (e) {
    failed = true;
    process.stdout.write(JSON.stringify({ out: job.out, error: String(e?.stack ?? e) }) + "\n");
  }
}
process.exit(failed ? 1 : 0);
