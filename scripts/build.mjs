import { build } from "esbuild";
import { cp, mkdir, rm } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const destination = join(root, "extension", "dist");
await rm(destination, { recursive: true, force: true });
await mkdir(destination, { recursive: true });
await build({
  entryPoints: {
    sidepanel: join(root, "extension/src/App.tsx"),
    background: join(root, "extension/src/background.ts"),
  },
  outdir: destination, bundle: true, minify: true, target: "chrome116",
  format: "iife", define: { "process.env.NODE_ENV": '"production"' },
});
for (const name of ["manifest.json", "sidepanel.html", "styles.css", "icons"]) {
  await cp(join(root, "extension", name), join(destination, name), { recursive: true });
}
for (const name of ["LICENSE", "THIRD_PARTY_NOTICES.txt"]) {
  await cp(join(root, name), join(destination, name));
}
console.log("Built extension/dist — load this folder in Chrome.");
