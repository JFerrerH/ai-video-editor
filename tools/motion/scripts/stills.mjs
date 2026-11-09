// Many Overlay (or Stage) stills from one bundle, with each still's text measurements (`measure` mode).
//
//   node scripts/stills.mjs < jobs.json
//   jobs.json: {"publicDir": "<dir>", "jobs": [{"props": "<props.json>", "frame": 36, "out": "<png>", "scale": 0.5,
//                "composition": "Overlay" | "Stage"}]}
//
// Prints one JSON line per job, in order: {"out", "measure": [{event, texts: [{text, box, size}]}] | null}.
// A job whose props say `"measure": true` logs its measurements from the page; the CLI's `remotion still`
// drops browser logs, which is why this script exists. A failed job prints {"out", "error"} and the
// script exits 1 after the rest.
import fs from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const { publicDir, jobs } = JSON.parse(fs.readFileSync(0, "utf8"));

const serveUrl = await bundle({ entryPoint: path.join(ROOT, "src", "index.ts"), publicDir, rspack: true });
// a free port of our own: two of these at once (a matrix, two builds) would race for Remotion's default 3000
const port = await new Promise((resolve, reject) => {
  const srv = net.createServer();
  srv.once("error", reject);
  srv.listen(0, "127.0.0.1", () => {
    const { port: p } = srv.address();
    srv.close(() => resolve(p));
  });
});
let failed = false;
for (const job of jobs) {
  const inputProps = JSON.parse(fs.readFileSync(job.props, "utf8"));
  let measure = null;
  try {
    const composition = await selectComposition({ serveUrl, id: job.composition ?? "Overlay", inputProps, logLevel: "error", port });
    await renderStill({
      serveUrl,
      composition,
      inputProps,
      frame: job.frame,
      output: job.out,
      scale: job.scale ?? 1,
      port,
      logLevel: "error",
      onBrowserLog: (log) => {
        if (log.text.startsWith("MEASURE ")) measure = JSON.parse(log.text.slice("MEASURE ".length));
      },
    });
    process.stdout.write(JSON.stringify({ out: job.out, measure }) + "\n");
  } catch (e) {
    failed = true;
    process.stdout.write(JSON.stringify({ out: job.out, error: e?.stack ? String(e.stack) : typeof e === "object" ? JSON.stringify(e) : String(e) }) + "\n");
  }
}
process.exit(failed ? 1 : 0);
