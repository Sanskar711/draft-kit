export type Fact = { id: string; text: string; confirmed: boolean; source?: "manual" | "resume" | "linkedin"; source_url?: string; source_filename?: string };
export type Profile = { name: string; headline: string; writing_style: string; facts: Fact[]; linkedin_profile_url?: string; linkedin_imported_at?: string; resume_filename?: string; resume_imported_at?: string };
export type Status = { connected: boolean; plan_enabled: boolean; email: string; pending: boolean; error: string; mode: "chatgpt" | "demo" };
export type Settings = { address: string; token: string; welcomeSeen: boolean };
export type Model = { id: string; name: string };
export type Job = { url: string; title: string; company: string; location: string; description: string; warnings: string[] };
export type StreamEvent = { type: string; text?: string; hashtags?: string[]; facts?: Fact[]; demo?: boolean; message?: string; code?: string; job?: Job };
export const EMPTY_PROFILE: Profile = { name: "", headline: "", writing_style: "", facts: [] };

export function localAddress(value: string): string {
  const url = new URL(value);
  if (url.protocol !== "http:" || url.hostname !== "127.0.0.1" ||
      url.username || url.password || url.search || url.hash ||
      (url.pathname !== "" && url.pathname !== "/")) {
    throw new Error("Use a local address such as http://127.0.0.1:1455.");
  }
  return url.origin;
}

export async function loadSettings(): Promise<Settings> {
  const data = await chrome.storage.local.get(["address", "token", "welcomeSeen"]);
  return {
    address: typeof data.address === "string" ? data.address : "http://127.0.0.1:1455",
    token: typeof data.token === "string" ? data.token : "",
    welcomeSeen: data.welcomeSeen === true,
  };
}

export async function saveSettings(settings: Settings) {
  await chrome.storage.local.set(settings);
}

export async function request<T>(
  settings: Settings, path: string, body?: unknown,
  method = body === undefined ? "GET" : "POST",
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(localAddress(settings.address) + path, {
      method, redirect: "error", signal: AbortSignal.timeout(35000),
      headers: {
        "Content-Type": "application/json",
        "X-Composer-Extension": chrome.runtime.id,
        ...(settings.token ? { "X-Composer-Token": settings.token } : {}),
      },
      ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
    });
  } catch {
    throw new Error("Start your local companion, then check the address and try again.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "The request could not finish.");
  return data as T;
}

export async function streamDraft(settings: Settings, body: unknown, signal: AbortSignal, onEvent: (event: StreamEvent) => void) {
  const response = await fetch(localAddress(settings.address) + "/generate", {
    method: "POST", signal, redirect: "error",
    headers: { "Content-Type": "application/json", "X-Composer-Token": settings.token, "X-Composer-Extension": chrome.runtime.id },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(data.message || "The request could not finish.");
  }
  if (!response.body) throw new Error("The companion returned no response stream.");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let doneSeen = false;
  try {
    while (true) {
      const chunk = await reader.read();
      buffer += decoder.decode(chunk.value, { stream: !chunk.done });
      if (buffer.length > 262144) throw new Error("The response was too large.");
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";
      if (chunk.done && buffer.trim()) { lines.push(buffer); buffer = ""; }
      for (const line of lines) {
        if (!line.trim()) continue;
        const event: StreamEvent = JSON.parse(line);
        if (event.type === "error") throw new Error(event.message || "The draft is incomplete.");
        if (event.type === "done") doneSeen = true;
        onEvent(event);
      }
      if (chunk.done) break;
    }
    if (!doneSeen) throw new Error("The connection ended before the draft finished.");
  } finally {
    // Cancelling also closes the upstream stream at the companion.
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
