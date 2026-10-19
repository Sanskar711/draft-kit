import assert from "node:assert/strict";
import { build } from "esbuild";
import { readFile, mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const state = join(root, ".test-state", "resume");
await mkdir(state, { recursive: true });
const output = join(state, "resume.mjs");
await build({ entryPoints: [join(root, "extension/src/resume.ts")], outfile: output, bundle: true, platform: "node", format: "esm" });
const { profileFromResume } = await import(pathToFileURL(output).href);
const previous = { name: "Manual name", headline: "Backend engineer", writing_style: "Concise", facts: [
  { id: "manual", text: "My pasted profile fact.", confirmed: true, source: "manual" },
  { id: "old", text: "Old résumé fact.", confirmed: true, source: "resume" },
] };
const capture = { filename: "resume.pdf", text: "Alex Rao\nExperience\nBuilt FastAPI APIs and reduced latency by 25%.\nEducation\nBachelor of Technology", warnings: [] };
const result = profileFromResume(capture, previous);
assert.equal(result.profile.name, previous.name);
assert.equal(result.profile.headline, previous.headline);
assert.equal(result.profile.writing_style, previous.writing_style);
assert(result.profile.facts.some(f => f.id === "manual"));
assert(!result.profile.facts.some(f => f.id === "old"));
assert(result.profile.facts.some(f => f.text.includes("25%")));
assert(result.profile.facts.filter(f => f.source === "resume").every(f => !f.confirmed && f.source_filename === "resume.pdf"));
console.log("PASS résumé fact conversion, review gate, retained pasted context and replaced résumé snapshot");
const large = profileFromResume({ ...capture, text: "Experience\n" + Array.from({ length: 2500 }, (_, i) => "Task " + i + " working with FastAPI and RabbitMQ.").join(" ") }, previous);
assert(large.profile.facts.length <= 60);
assert(large.profile.facts.every(f => f.text.length <= 1500));
assert(large.profile.facts.reduce((n,f) => n + f.text.length, 0) <= 24000);
assert(large.warnings.some(note => note.includes("context limit")));
console.log("PASS bounded facts and explicit omission notes");
const manifest = JSON.parse(await readFile(join(root, "extension/manifest.json"), "utf8"));
assert(!manifest.permissions.includes("scripting"));
assert(!manifest.optional_host_permissions);
console.log("PASS no LinkedIn access or page-injection permission");
