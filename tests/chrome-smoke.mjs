import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { existsSync } from "node:fs";
import { mkdir, readFile, rm } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const state = join(root, ".test-state", "chrome");
await rm(state, { recursive: true, force: true });
await mkdir(state, { recursive: true });
const extension = join(root, "extension", "dist");
const manifest = JSON.parse(await readFile(join(extension, "manifest.json")));
assert.deepEqual(manifest.host_permissions, ["http://127.0.0.1/*"]);
assert.equal(manifest.optional_host_permissions, undefined);
assert.equal(manifest.content_scripts, undefined);
assert(!manifest.permissions.includes("cookies"));
const python = process.env.COMPOSER_TEST_PYTHON || join(root, ".venv", ...(process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
const child = spawn(python, ["-m", "companion", "--demo", "--port", "1466"], {
  cwd: root, env: { ...process.env,
    CAREER_COMPOSER_DATA_DIR: join(state, "data"),
    CAREER_COMPOSER_KEY_DIR: join(state, "keys"),
  }, stdio: ["ignore", "pipe", "pipe"],
});
let output = "";
let startupErrors = "";
child.stdout.on("data", data => { output += data; });
child.stderr.on("data", data => { startupErrors += data; });
let context;
try {
  const deadline = Date.now() + 20000;
  let code;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error("Companion failed to start: " + startupErrors);
    code = /Pairing code: (\S+)/.exec(output)?.[1];
    if (code) {
      try { if ((await fetch("http://127.0.0.1:1466/health")).ok) break; } catch {}
    }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert(code, "The companion should print a pairing code.");
  const runtimeBrowser = process.env.COMPOSER_CHROMIUM_PATH;
  context = await chromium.launchPersistentContext(join(state, "browser"), {
    channel: "chromium", headless: true,
    ignoreDefaultArgs: ["--disable-extensions"],
    ...(runtimeBrowser && existsSync(runtimeBrowser) ? { executablePath: runtimeBrowser } : {}),
    args: ["--no-sandbox", "--disable-extensions-except=" + extension, "--load-extension=" + extension],
    viewport: { width: 390, height: 1020 },
  });
  let [worker] = context.serviceWorkers();
  if (!worker) worker = await context.waitForEvent("serviceworker", { timeout: 15000 });
  const id = worker.url().split("/")[2];
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  await page.goto("chrome-extension://" + id + "/sidepanel.html");
  await page.getByLabel("Companion address").fill("http://127.0.0.1:1466");
  await page.getByLabel("Pairing code", { exact: true }).fill(code);
  await page.getByRole("button", { name: "Pair companion", exact: true }).click();
  await page.getByText("Paired and reachable", { exact: true }).waitFor();
  await page.getByText("Your extension is paired.", { exact: true }).waitFor();
  console.log("PASS extension load, local pairing, and connection");

  await page.getByRole("button", { name: "My context", exact: true }).click();
  await page.getByText("Try a sample profile", { exact: true }).click();
  await page.getByRole("button", { name: "Load fictional sample", exact: true }).click();
  await page.getByLabel("I have checked these facts").check();
  await page.getByRole("button", { name: "Save my context", exact: true }).click();
  await page.getByText("Your professional context is saved.", { exact: true }).waitFor();
  await page.getByRole("button", { name: "DM", exact: true }).click();
  await page.getByLabel("Job description or link").fill("Backend Engineer. Requirements: Python, FastAPI and payment webhooks.");
  await page.getByRole("button", { name: "Generate demo draft", exact: true }).click();
  await page.getByRole("button", { name: "Copy draft", exact: true }).waitFor();
  assert((await page.getByLabel("Draft", { exact: true }).inputValue()).includes("Alex Rao"));
  await page.getByRole("button", { name: "Copy draft", exact: true }).click();
  await page.getByText("Draft copied. Review it before sending.", { exact: true }).waitFor();
  console.log("PASS profile save, grounded demo DM, streaming, and clipboard");

  await page.getByRole("button", { name: "Post", exact: true }).click();
  await page.getByLabel("What do you want to share?").fill("Share a project lesson.");
  assert(await page.getByRole("button", { name: "Generate demo draft", exact: true }).isDisabled());
  await page.getByRole("button", { name: "Reflective", exact: true }).click();
  await page.getByRole("button", { name: "Generate demo draft", exact: true }).click();
  await page.getByRole("button", { name: "#Learning", exact: true }).waitFor();
  await page.getByRole("button", { name: "#Learning", exact: true }).click();
  assert.equal(await page.getByRole("button", { name: "#Learning", exact: true }).getAttribute("aria-pressed"), "true");
  assert(!(await page.getByLabel("Draft", { exact: true }).inputValue()).includes("HASHTAG_SUGGESTIONS:"));
  await page.getByRole("button", { name: "Copy draft", exact: true }).click();
  await page.getByText("Draft copied. Review it before sending.", { exact: true }).waitFor();
  console.log("PASS required post tone, selectable hashtags, and copy composition");

  await page.screenshot({ path: join(state, "post.png"), fullPage: true });
  await page.getByRole("button", { name: "My context", exact: true }).click();
  await page.reload();
  await page.getByRole("button", { name: "My context", exact: true }).click();
  assert.equal(await page.getByLabel("Your name", { exact: true }).inputValue(), "Alex Rao");
  const behavior = await worker.evaluate(async () => chrome.sidePanel.getPanelBehavior());
  assert.equal(behavior.openPanelOnActionClick, true);
  assert.deepEqual(errors, []);
  console.log("PASS persisted profile, side-panel configuration, and no page errors");
} finally {
  await context?.close();
  child.kill("SIGTERM");
  if (child.exitCode === null) {
    await Promise.race([once(child, "exit"), new Promise(resolve => setTimeout(resolve, 2000))]);
    if (child.exitCode === null) child.kill("SIGKILL");
  }
}
