import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { readFile, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { webcrypto } from "node:crypto";
import { JSDOM, VirtualConsole } from "jsdom";
import { build } from "esbuild";
import { getByRole, getByLabelText, getByText, waitFor, fireEvent } from "@testing-library/dom";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const state = join(root, ".test-state", "ui");
await rm(state, { recursive: true, force: true });
await mkdir(state, { recursive: true });
const python = process.env.COMPOSER_TEST_PYTHON || join(root, ".venv", ...(process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
const child = spawn(python, ["-m", "companion", "--demo", "--port", "1467"], {
  cwd: root, env: { ...process.env,
    CAREER_COMPOSER_DATA_DIR: join(state, "data"),
    CAREER_COMPOSER_KEY_DIR: join(state, "keys"),
  }, stdio: ["ignore", "pipe", "pipe"],
});
let stdout = "";
child.stdout.on("data", data => { stdout += data; });
let stderr = "";
child.stderr.on("data", data => { stderr += data; });
let dom;
try {
  const deadline = Date.now() + 15000;
  let code;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error("Companion startup failed: " + stderr);
    code = /Pairing code: (\S+)/.exec(stdout)?.[1];
    if (code) {
      try { if ((await fetch("http://127.0.0.1:1467/health")).ok) break; } catch {}
    }
    await new Promise(resolve => setTimeout(resolve, 50));
  }
  assert(code);
  const errors = [];
  const console = new VirtualConsole();
  console.on("jsdomError", error => errors.push(error.message));
  dom = new JSDOM(await readFile(join(root, "extension/dist/sidepanel.html"), "utf8"), {
    url: "https://extension.test/sidepanel.html", runScripts: "outside-only",
    pretendToBeVisual: true, virtualConsole: console,
  });
  const window = dom.window;
  const style = window.document.createElement("style");
  style.textContent = await readFile(join(root, "extension/styles.css"), "utf8");
  window.document.head.append(style);
  Object.defineProperty(window, "crypto", { value: webcrypto });
  window.TextDecoder = TextDecoder;
  window.TextEncoder = TextEncoder;
  window.AbortController = AbortController;
  window.AbortSignal = AbortSignal;
  let clipboard = "";
  Object.defineProperty(window.navigator, "clipboard", { value: {
    writeText: async value => { clipboard = value; },
  } });
  const settings = { address: "http://127.0.0.1:1467", token: "", welcomeSeen: false };
  window.chrome = {
    runtime: { id: "a".repeat(32), getManifest: () => ({
      version: "0.9.0", permissions: ["sidePanel", "storage", "clipboardWrite"],
    }) },
    storage: { local: {
      get: async () => ({ ...settings }),
      set: async values => Object.assign(settings, values),
    } },
    tabs: { create: async () => {} },
  };
  let quota = false;
  let releaseProfile;
  const profileGate = new Promise(resolve => { releaseProfile = resolve; });
  let delayFirstProfile = true;
  let blockedJob = false;
  const generateBodies = [];
  window.fetch = async (url, options) => {
    if (new URL(url).pathname === "/generate") {
      const sent = JSON.parse(options.body);
      generateBodies.push(sent);
      if (sent.revision === "custom" && !quota) {
        const revised = sent.current_draft + "\n\nA concise, warmer closing.";
        return new Response([
          { type: "draft_delta", text: revised },
          { type: "result", text: revised, hashtags: sent.mode === "post" ? ["#Learning"] : [], facts: [], demo: true },
          { type: "done" },
        ].map(event => JSON.stringify(event)).join("\n") + "\n", { headers: { "Content-Type": "application/x-ndjson" } });
      }
      if (sent.job_input?.startsWith("https://jobs.example.com/")) {
        const job = { url: sent.job_input, title: "Backend Engineer", company: "Example Labs", location: "Bengaluru", description: "Build Python FastAPI services with reliable webhooks.", warnings: [] };
        const events = blockedJob ? [
          { type: "status", message: "Reading job…" },
          { type: "error", code: "job_unavailable", message: "This job page could not be read. Paste the job description instead." },
        ] : [
          { type: "status", message: "Reading job…" }, { type: "job", job },
          { type: "context", facts: [] }, { type: "draft_delta", text: "Hi,\n\nI'm Alex Rao. I'm interested in the Backend Engineer role at Example Labs." },
          { type: "result", text: "Hi,\n\nI'm Alex Rao. I'm interested in the Backend Engineer role at Example Labs.", hashtags: [], facts: [], demo: true }, { type: "done" },
        ];
        return new Response(events.map(event => JSON.stringify(event)).join("\n") + "\n", { headers: { "Content-Type": "application/x-ndjson" } });
      }
    }
    if (quota && new URL(url).pathname === "/generate") {
      return new Response(
        '{"type":"draft_delta","text":"Partial text"}\n{"type":"error","code":"usage_limit","message":"Usage limit reached."}\n',
        { headers: { "Content-Type": "application/x-ndjson" } },
      );
    }
    const response = await fetch(url, options);
    if (new URL(url).pathname === "/profile" && delayFirstProfile) {
      delayFirstProfile = false;
      await profileGate;
    }
    return response;
  };
  window.eval(await readFile(join(root, "extension/dist/sidepanel.js"), "utf8"));
  const body = window.document.body;
  const wait = callback => waitFor(callback, { container: body, timeout: 6000, interval: 20 });
  const button = name => getByRole(body, "button", { name, exact: true });
  async function fill(label, value) {
    const element = await wait(() => getByLabelText(body, label, { exact: true }));
    const prototype = element.tagName === "TEXTAREA" ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
    Object.getOwnPropertyDescriptor(prototype, "value").set.call(element, value);
    fireEvent.input(element, { target: { value } });
    await new Promise(resolve => setTimeout(resolve, 0));
  }
  await wait(() => assert(button("Pair companion")));
  await fill("Pairing code", code);
  button("Pair companion").click();
  await wait(() => assert(getByText(body, "Paired and reachable", { exact: true })));
  assert(settings.token.length > 20);
  globalThis.console.log("PASS UI pairing through real local HTTP companion (no Origin header)");

  button("My context").click();
  await wait(() => assert(getByText(body, "Try a sample profile", { exact: true })));
  getByText(body, "Try a sample profile", { exact: true }).click();
  button("Load fictional sample").click();
  await wait(() => assert.equal(getByLabelText(body, "Your name", { exact: true }).value, "Alex Rao"));
  // Release a delayed initialization response after the user starts editing.
  releaseProfile();
  await wait(() => assert(getByText(body, "Your extension is paired.", { exact: true })));
  assert.equal(getByLabelText(body, "Your name", { exact: true }).value, "Alex Rao");
  getByLabelText(body, /I have checked these facts/).click();
  await wait(() => assert(getByLabelText(body, /I have checked these facts/).checked));
  await wait(() => assert(!button("Save my context").disabled));
  button("Save my context").click();
  await wait(() => assert(getByText(body, "Your professional context is saved.", { exact: true })));
  button("DM").click();
  await fill("Job description or link", "Backend Engineer. Requirements: Python, FastAPI and payment webhooks.");
  assert.equal(body.querySelector("#recipient"), null);
  assert.equal(body.querySelector("#thread"), null);
  assert.equal(body.querySelector(".options").open, false);
  assert.equal(window.getComputedStyle(getByLabelText(body, "Job description or link")).fontSize, "16px");
  button("Generate demo draft").click();
  await wait(() => assert(button("Copy draft")));
  assert(getByLabelText(body, "Draft", { exact: true }).value.includes("Alex Rao"));
  assert(getByLabelText(body, "Draft", { exact: true }).value.startsWith("Hi,"));
  assert(!getByLabelText(body, "Draft", { exact: true }).value.includes("recipient name"));
  assert.equal(window.getComputedStyle(getByLabelText(body, "Draft")).fontSize, "17px");
  assert(generateBodies[0].job_input.includes("FastAPI"));
  assert.equal(generateBodies[0].dm_intent, "referral");
  assert(!("recipient_context" in generateBodies[0]) && !("thread" in generateBodies[0]));
  button("Copy draft").click();
  await wait(() => assert(clipboard.includes("Alex Rao")));
  globalThis.console.log("PASS reviewed profile, streaming demo DM, editable result, and copy handler");

  getByLabelText(body, "Contact the hiring team").click();
  await wait(() => assert(getByLabelText(body, "Contact the hiring team").checked));
  assert.equal(getByLabelText(body, "Ask an employee for a referral").checked, false);
  button("Generate demo draft").click();
  await wait(() => assert(getByLabelText(body, "Draft").value.includes("next steps in the hiring process")));
  await wait(() => assert(!button("Copy draft").disabled));
  assert.equal(generateBodies.at(-1).dm_intent, "hiring");
  assert(!getByLabelText(body, "Draft").value.includes("referring"));
  assert(button("Apply changes").disabled);
  const editedDM = "Hi,\n\nI'm Alex Rao. I built reliable payment webhooks. This sentence was edited manually.";
  await fill("Draft", editedDM);
  await fill("What should change?", "Keep my edits and add a concise, warmer closing.");
  await wait(() => assert(!button("Apply changes").disabled));
  button("Apply changes").click();
  await wait(() => assert(getByLabelText(body, "Draft").value.endsWith("A concise, warmer closing.")));
  const revisionBody = generateBodies.at(-1);
  assert.equal(revisionBody.current_draft, editedDM);
  assert.equal(revisionBody.modification, "Keep my edits and add a concise, warmer closing.");
  assert.equal(revisionBody.revision, "custom");
  assert.equal(revisionBody.dm_intent, "hiring");
  button("Restore previous draft").click();
  await wait(() => assert.equal(getByLabelText(body, "Draft").value, editedDM));
  globalThis.console.log("PASS distinct referral/hiring choices, custom feedback, manual draft edits and restore");

  await fill("Job description or link", "https://jobs.example.com/backend");
  button("Generate demo draft").click();
  await wait(() => assert(getByText(body, "Backend Engineer · Example Labs", { exact: true })));
  await wait(() => assert(button("Copy draft")));
  assert(getByLabelText(body, "Draft", { exact: true }).value.includes("Example Labs"));
  button("Copy draft").click();
  await wait(() => assert(clipboard.includes("Backend Engineer")));
  assert(getByText(body, "Job source ↗").href.endsWith("/backend"));
  globalThis.console.log("PASS automatic link request, role preview, generic greeting and larger input/draft text");
  blockedJob = true;
  button("Generate demo draft").click();
  await wait(() => assert(getByText(body, "This job page could not be read. Paste the job description instead.", { exact: true })));
  assert.equal(getByLabelText(body, "Job description or link").value, "https://jobs.example.com/backend");
  assert.equal(getByLabelText(body, "Draft").value, "");
  button("Restore previous draft").click();
  await wait(() => assert(getByLabelText(body, "Draft").value.includes("Example Labs")));
  globalThis.console.log("PASS blocked-link message, retained job input and previous-draft restoration");

  button("Post").click();
  await fill("What do you want to share?", "Share a project lesson.");
  assert(button("Generate demo draft").disabled, "Post tone must be chosen.");
  button("Reflective").click();
  await wait(() => assert(!button("Generate demo draft").disabled));
  button("Generate demo draft").click();
  await wait(() => assert(button("#Learning")));
  button("#Learning").click();
  await wait(() => assert.equal(button("#Learning").getAttribute("aria-pressed"), "true"));
  button("Copy draft").click();
  await wait(() => assert(clipboard.endsWith("#Learning")));
  assert(!clipboard.includes("#CareerGrowth"));
  assert(!clipboard.includes("HASHTAG_SUGGESTIONS:"));
  globalThis.console.log("PASS required tone, optional hashtag selection, and copied post formatting");

  assert.equal(getByLabelText(body, "What should change?").value, "", "Revision feedback is separate for DM and Post.");
  await fill("Draft", "A manually edited post about payment reliability.");
  await fill("What should change?", "Add a concise, warmer closing.");
  button("Apply changes").click();
  await wait(() => assert(getByLabelText(body, "Draft").value.endsWith("A concise, warmer closing.")));
  assert.equal(generateBodies.at(-1).mode, "post");
  assert.equal(generateBodies.at(-1).current_draft, "A manually edited post about payment reliability.");
  const goodDraft = getByLabelText(body, "Draft", { exact: true }).value;
  globalThis.console.log("PASS post revisions use the current edited draft with separate feedback");

  quota = true;
  button("Shorten").click();
  await wait(() => assert(getByText(body, "Usage limit reached.", { exact: true })));
  assert.equal(getByLabelText(body, "What do you want to share?", { exact: true }).value, "Share a project lesson.");
  assert.equal(getByLabelText(body, "Draft", { exact: true }).value, "Partial text");
  assert(button("Copy partial draft"));
  button("Restore previous draft").click();
  await wait(() => assert.equal(getByLabelText(body, "Draft", { exact: true }).value, goodDraft));
  assert(button("Copy draft"));
  globalThis.console.log("PASS mid-stream failure, preserved prompt, explicit partial-copy, and draft restore");

  button("My context").click();
  await wait(() => assert.equal(getByLabelText(body, "Your name", { exact: true }).value, "Alex Rao"));
  const upload = file => {
    const input = getByLabelText(body, "Upload résumé");
    Object.defineProperty(input, "files", { configurable: true, value: [file] });
    fireEvent.change(input);
  };
  upload(new window.File(["not supported"], "resume.exe"));
  await wait(() => assert(getByText(body, "Choose a PDF, DOCX or TXT résumé.", { exact: true })));
  assert.equal(getByLabelText(body, "Your name", { exact: true }).value, "Alex Rao");
  upload(new window.File(["Alex Rao\nExperience\nBuilt FastAPI APIs and reduced latency by 25%.\nEducation\nBachelor of Technology."], "resume.txt", { type: "text/plain" }));
  await wait(() => assert(getByText(body, "Résumé imported. Review and save.", { exact: true })));
  assert(getByLabelText(body, "Experience & achievements", { exact: true }).value.includes("25%"));
  assert.equal(getByLabelText(body, /I have checked these facts/).checked, false);
  const approvedBefore = await fetch("http://127.0.0.1:1467/profile", { headers: { "X-Composer-Extension": "a".repeat(32), "X-Composer-Token": settings.token } }).then(r => r.json());
  assert(!approvedBefore.facts.some(f => f.source === "resume"), "Import must not save unreviewed facts.");
  assert(getByLabelText(body, "Experience & achievements").value.includes("Coordinated a cross-functional project"), "Keep pasted/manual context.");
  getByLabelText(body, /I have checked these facts/).click();
  await wait(() => assert(getByLabelText(body, /I have checked these facts/).checked));
  button("Save my context").click();
  await wait(() => assert(getByText(body, "Your professional context is saved.", { exact: true })));
  const approvedAfter = await fetch("http://127.0.0.1:1467/profile", { headers: { "X-Composer-Extension": "a".repeat(32), "X-Composer-Token": settings.token } }).then(r => r.json());
  assert(approvedAfter.facts.some(f => f.source === "resume" && f.confirmed && f.text.includes("25%")));
  assert.equal(approvedAfter.resume_filename, "resume.txt");
  globalThis.console.log("PASS résumé upload, invalid file handling, retained pasted context, review gate and saved provenance");
  assert(errors.length === 0, errors.join("\n"));
  globalThis.console.log("PASS tab state and no client runtime errors");
} finally {
  dom?.window.close();
  child.kill("SIGTERM");
  if (child.exitCode === null) {
    await Promise.race([once(child, "exit"), new Promise(resolve => setTimeout(resolve, 2000))]);
    if (child.exitCode === null) child.kill("SIGKILL");
  }
}
