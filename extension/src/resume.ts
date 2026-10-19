import { request, type Fact, type Profile, type Settings } from "./api";

export type ResumeCapture = { filename: string; text: string; warnings: string[] };

export async function uploadResume(settings: Settings, file: File): Promise<ResumeCapture> {
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) throw new Error("Choose a PDF, DOCX or TXT résumé.");
  if (!file.size || file.size > 5 * 1024 * 1024) throw new Error("Choose a résumé under 5 MB.");
  const content = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1] || "");
    reader.onerror = () => reject(new Error("Your résumé could not be opened. Choose it again."));
    reader.readAsDataURL(file);
  });
  return request<ResumeCapture>(settings, "/resume/import", { filename: file.name, content_base64: content });
}

export function profileFromResume(capture: ResumeCapture, previous: Profile): { profile: Profile; warnings: string[] } {
  const retained = previous.facts.filter(fact => fact.source !== "resume" && fact.text.trim());
  const warnings = [...capture.warnings];
  const lines = capture.text.split(/\r?\n/).map(line => line.replace(/[ \t]+/g, " ").trim()).filter(Boolean);
  const chunks: string[] = [];
  let chunk = "";
  for (const line of lines) {
    if (/^(experience|education|projects|skills|technical skills|work experience|professional experience)$/i.test(line) && chunk) {
      chunks.push(chunk); chunk = "";
    }
    for (const word of line.split(/\s+/)) {
      for (let start = 0; start < word.length; start += 1300) {
        const part = word.slice(start, start + 1300);
        if ((chunk + " " + part).length > 1300) { if (chunk) chunks.push(chunk); chunk = ""; }
        chunk += (chunk ? " " : "") + part;
      }
    }
  }
  if (chunk) chunks.push(chunk);
  const facts: Fact[] = [...retained];
  const seen = new Set(facts.map(f => f.text.toLowerCase()));
  let total = facts.reduce((count, fact) => count + fact.text.length, 0);
  let skipped = 0;
  for (const value of chunks) {
    const text = "Résumé: " + value;
    if (seen.has(text.toLowerCase())) continue;
    if (facts.length >= 60 || total + text.length > 24000) { skipped++; continue; }
    facts.push({ id: crypto.randomUUID(), text, confirmed: false, source: "resume", source_filename: capture.filename });
    seen.add(text.toLowerCase()); total += text.length;
  }
  if (skipped) warnings.push("Some résumé text exceeded the context limit. Keep the most relevant facts.");
  return { profile: { ...previous, facts, resume_filename: capture.filename, resume_imported_at: new Date().toISOString() }, warnings };
}

// Older profile exports may contain LinkedIn provenance. Retain it without page access.
export function canonicalProfileUrl(value: unknown): string {
  if (typeof value !== "string" || value.length > 512) return "";
  try {
    const url = new URL(value);
    return url.origin === "https://www.linkedin.com" && /^\/in\/[^/]+\/?$/.test(url.pathname) && !url.username && !url.password
      ? url.origin + url.pathname.replace(/\/?$/, "/") : "";
  } catch { return ""; }
}
