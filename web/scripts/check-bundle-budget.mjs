import { gzipSync } from "node:zlib";
import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const assetDir = new URL("../dist/assets/", import.meta.url);
const assetPath = fileURLToPath(assetDir);
const files = readdirSync(assetPath).filter((name) => name.endsWith(".js"));

const budgets = [
  { label: "main entry", pattern: /^index-.*\.js$/, gzipKiB: 250, required: true },
  { label: "project workspace", pattern: /^ProjectWorkspace-.*\.js$/, gzipKiB: 220, required: true },
  { label: "sandbox Babel runtime", pattern: /^babel-.*\.js$/, gzipKiB: 650, required: true },
];

let failed = false;
for (const budget of budgets) {
  const matches = files.filter((name) => budget.pattern.test(name));
  if (budget.required && matches.length !== 1) {
    console.error(`[bundle-budget] ${budget.label}: expected one chunk, found ${matches.length}`);
    failed = true;
    continue;
  }
  for (const name of matches) {
    const gzipBytes = gzipSync(readFileSync(join(assetPath, name))).byteLength;
    const gzipKiB = gzipBytes / 1024;
    const status = gzipKiB <= budget.gzipKiB ? "PASS" : "FAIL";
    console.log(`[bundle-budget] ${status} ${budget.label}: ${gzipKiB.toFixed(2)} KiB / ${budget.gzipKiB} KiB gzip`);
    if (gzipKiB > budget.gzipKiB) failed = true;
  }
}

if (failed) process.exit(1);
