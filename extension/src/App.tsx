import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { EMPTY_PROFILE, Fact, Job, Model, Profile, Settings, Status, loadSettings, localAddress, request, saveSettings, streamDraft } from "./api";
import { uploadResume, profileFromResume, canonicalProfileUrl } from "./resume";

type Mode = "dm" | "post";
type Tab = Mode | "profile" | "settings";
type Composer = {
  prompt: string; tone: string; length: string; jobInput: string; job: Job | null;
  dmIntent: "referral" | "hiring"; modification: string;
  language: string; hashtags: boolean; emoji: boolean; includeProfile: boolean;
  text: string; suggestions: string[]; selectedTags: string[]; facts: Fact[];
  phase: "empty" | "streaming" | "complete" | "incomplete";
};
const initialComposer = (mode: Mode): Composer => ({
  prompt: "", tone: mode === "dm" ? "Professional" : "", length: mode === "dm" ? "short" : "medium",
  jobInput: "", job: null, language: "English", hashtags: true, emoji: false, includeProfile: true,
  dmIntent: "referral", modification: "",
  text: "", suggestions: [], selectedTags: [], facts: [], phase: "empty",
});
const TONES = ["Professional", "Conversational", "Reflective", "Confident"];
const SAMPLE: Profile = {
  name: "Alex Rao", headline: "Professional · collaboration and problem-solving",
  writing_style: "Clear, friendly and concise. Avoid exaggerated enthusiasm.",
  facts: [
    { id: "sample-1", text: "Coordinated a cross-functional project from planning to delivery.", confirmed: true },
    { id: "sample-2", text: "Improved a team process, reducing turnaround time by 20%.", confirmed: true },
  ],
};

function Icon({ name }: { name: "spark" | "dm" | "post" | "profile" | "settings" }) {
  const paths = {
    spark: <><path d="m12 3 2.1 6.9L21 12l-6.9 2.1L12 21l-2.1-6.9L3 12l6.9-2.1Z"/><path d="m20 2 .6 1.4L22 4l-1.4.6L20 6l-.6-1.4L18 4l1.4-.6Z"/></>,
    dm: <path d="M20 11.5a7.7 7.7 0 0 1-8 7.5H6l-4 3V11.5A7.7 7.7 0 0 1 10 4h2a7.7 7.7 0 0 1 8 7.5ZM7 10h8M7 14h5"/>,
    post: <><path d="M5 3h10l4 4v14H5ZM15 3v5h4M8 12h8M8 16h6"/></>,
    profile: <><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a8 8 0 0 1 16 0v2"/></>,
    settings: <><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/></>,
  };
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function App() {
  const installedVersion = chrome.runtime.getManifest().version;
  const [settings, setSettings] = useState<Settings>({ address: "http://127.0.0.1:1455", token: "", welcomeSeen: false });
  const [address, setAddress] = useState(settings.address);
  const [loaded, setLoaded] = useState(false);
  const [tab, setTab] = useState<Tab>("dm");
  const [status, setStatus] = useState<Status | null>(null);
  const [online, setOnline] = useState(false);
  const [models, setModels] = useState<Model[]>([]);
  const [model, setModel] = useState("");
  const [profile, setProfile] = useState<Profile>(EMPTY_PROFILE);
  const profileDirty = useRef(false);
  const [savedProfile, setSavedProfile] = useState<Profile>(EMPTY_PROFILE);
  const [confirmed, setConfirmed] = useState(false);
  const [pairCode, setPairCode] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [working, setWorking] = useState(false);
  const [importWarnings, setImportWarnings] = useState<string[]>([]);
  const [generating, setGenerating] = useState(false);
  const [generationLabel, setGenerationLabel] = useState("Writing…");
  const [welcome, setWelcome] = useState(false);
  const [composers, setComposers] = useState({ dm: initialComposer("dm"), post: initialComposer("post") });
  const [backups, setBackups] = useState<Partial<Record<Mode, Composer>>>({});
  const abort = useRef<AbortController | null>(null);
  const settingsRef = useRef(settings);
  settingsRef.current = settings;
  const polling = useRef(false);
  const noticeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mode: Mode = tab === "post" ? "post" : "dm";
  const composer = composers[mode];
  const demo = status?.mode === "demo";
  const canGenerate = online && settings.token && (demo || status?.plan_enabled) && model && !generating;

  function flash(message: string) {
    setNotice(message);
    if (noticeTimer.current) clearTimeout(noticeTimer.current);
    noticeTimer.current = setTimeout(() => setNotice(""), 5000);
  }
  function update(mode: Mode, patch: Partial<Composer>) {
    setComposers(previous => ({ ...previous, [mode]: { ...previous[mode], ...patch } }));
  }
  function editProfile(next: Profile) {
    profileDirty.current = true;
    setProfile(next);
  }
  async function importResume(file?: File) {
    if (!file) return;
    setWorking(true); setError("");
    try {
      const capture = await uploadResume(settings, file);
      const imported = profileFromResume(capture, profile);
      editProfile(imported.profile);
      setImportWarnings(imported.warnings);
      setConfirmed(false);
      flash("Résumé imported. Review and save.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Your résumé could not be read.");
    } finally { setWorking(false); }
  }
  async function refresh(next = settingsRef.current, quiet = false) {
    let companionReached = false;
    try {
      await request(next, "/health");
      companionReached = true;
      setOnline(true);
      if (!next.token) { setStatus(null); return; }
      const [connection, currentProfile] = await Promise.all([
        request<Status>(next, "/auth/status"), request<Profile>(next, "/profile"),
      ]);
      setStatus(connection);
      setSavedProfile(currentProfile);
      // Refreshes during sign-in must not replace unsaved profile edits.
      if (!quiet && !profileDirty.current) {
        setProfile(currentProfile);
        setConfirmed(currentProfile.facts.length > 0 && currentProfile.facts.every(f => f.confirmed));
      }
      if (connection.plan_enabled || connection.mode === "demo") {
        const data = await request<{ models: Model[] }>(next, "/models");
        setModels(data.models);
        setModel(previous => data.models.some(m => m.id === previous) ? previous : data.models[0]?.id || "");
        if (connection.plan_enabled && !next.welcomeSeen) setWelcome(true);
      } else { setModels([]); setModel(""); }
      if (connection.error) setError(connection.error);
      else if (!quiet) setError("");
    } catch (cause) {
      if (!quiet) setError(cause instanceof Error ? cause.message : "Connection failed.");
      setOnline(companionReached);
      setModels([]); setModel("");
    }
  }
  useEffect(() => {
    void loadSettings().then(next => {
      setSettings(next); setAddress(next.address); setLoaded(true);
      if (!next.token) setTab("settings");
      void refresh(next);
    }).catch(() => { setLoaded(true); setTab("settings"); setError("Extension settings could not be loaded."); });
    return () => {
      abort.current?.abort();
      if (noticeTimer.current) clearTimeout(noticeTimer.current);
    };
  }, []);
  useEffect(() => {
    if (!status?.pending) return;
    const timer = setInterval(() => {
      if (polling.current) return;
      polling.current = true;
      void refresh(settingsRef.current, true).finally(() => { polling.current = false; });
    }, 2000);
    return () => clearInterval(timer);
  }, [status?.pending]);

  async function pair() {
    setWorking(true); setError("");
    try {
      const base = localAddress(address);
      const next = { ...settings, address: base, token: "" };
      const data = await request<{ pair_token: string }>(next, "/pair", { code: pairCode, extension_id: chrome.runtime.id });
      next.token = data.pair_token;
      await saveSettings(next);
      setSettings(next); setAddress(base); setPairCode("");
      await refresh(next); flash("Your extension is paired.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Pairing failed."); }
    finally { setWorking(false); }
  }
  async function signIn() {
    setWorking(true); setError("");
    try {
      const data = await request<{ url: string }>(settings, "/auth/start", {});
      const url = new URL(data.url);
      if (url.origin !== "https://auth.openai.com" || url.pathname !== "/api/accounts/authorize") throw new Error("Unexpected sign-in address.");
      await chrome.tabs.create({ url: data.url });
      await refresh(settings, true);
      flash("Finish sign-in in the new tab, then return here.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Sign-in failed."); }
    finally { setWorking(false); }
  }
  async function disconnect() {
    setWorking(true); setError("");
    abort.current?.abort();
    try {
      const data = await request<{ message: string }>(settings, "/auth/logout", {});
      await refresh(settings, true); flash(data.message);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Disconnect failed."); }
    finally { setWorking(false); }
  }
  async function clearProfile() {
    if (!window.confirm("Delete your saved professional profile?")) return;
    setWorking(true); setError("");
    try {
      await request(settings, "/profile", undefined, "DELETE");
      profileDirty.current = false;
      setProfile(EMPTY_PROFILE); setSavedProfile(EMPTY_PROFILE); setConfirmed(false);
      setImportWarnings([]);
      flash("Your profile was cleared.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not clear profile."); }
    finally { setWorking(false); }
  }
  function exportProfile() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(savedProfile, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url; link.download = "draft-kit-profile.json"; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function importProfile(file?: File) {
    if (!file) return;
    try {
      if (file.size > 131072) throw new Error("Choose a smaller profile file.");
      const data = JSON.parse(await file.text());
      if (typeof data.name !== "string" || !Array.isArray(data.facts) || data.facts.length > 60 ||
          data.facts.some((f: Fact) => typeof f.text !== "string")) throw new Error("Choose an exported draft-kit profile.");
      editProfile({
        name: data.name, headline: typeof data.headline === "string" ? data.headline : "",
        writing_style: typeof data.writing_style === "string" ? data.writing_style : "",
        linkedin_profile_url: canonicalProfileUrl(data.linkedin_profile_url),
        linkedin_imported_at: typeof data.linkedin_imported_at === "string" ? data.linkedin_imported_at : "",
        resume_filename: typeof data.resume_filename === "string" ? data.resume_filename : "",
        resume_imported_at: typeof data.resume_imported_at === "string" ? data.resume_imported_at : "",
        facts: data.facts.map((f: Fact) => ({
          id: crypto.randomUUID(), text: f.text, confirmed: false,
          source: f.source === "resume" ? "resume" : f.source === "linkedin" ? "linkedin" : "manual",
          source_url: canonicalProfileUrl(f.source_url),
          source_filename: typeof f.source_filename === "string" ? f.source_filename : "",
        })),
      });
      setConfirmed(false); flash("Imported. Review the facts, then save.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Could not import profile."); }
  }
  async function generate(revision = "") {
    const current = composers[mode];
    if (!canGenerate) { setTab("settings"); return; }
    if (!(mode === "dm" ? current.jobInput : current.prompt).trim()) { setError(mode === "dm" ? "Paste a JD or job link." : "Add your post idea."); return; }
    if (!current.tone.trim()) { setError("Choose a tone before generating your post."); return; }
    if (revision && !current.text.trim()) { setError("Write a draft first."); return; }
    if (revision === "custom" && !current.modification.trim()) { setError("Describe your changes."); return; }
    setGenerating(true); setGenerationLabel(revision ? "Revising…" : "Writing…"); setError("");
    if (current.text.trim()) setBackups(previous => ({ ...previous, [mode]: { ...current } }));
    const controller = new AbortController();
    abort.current = controller;
    update(mode, { text: "", phase: "streaming", suggestions: [], selectedTags: [], facts: [], job: revision ? current.job : null });
    let draft = "";
    let resultSeen = false;
    try {
      await streamDraft(settings, {
        mode, model, prompt: mode === "dm" ? (current.dmIntent === "referral" ? "Write a concise LinkedIn DM to an employee asking for a referral for this job." : "Write a concise LinkedIn DM to the hiring team expressing interest in this job and asking about next steps.") : current.prompt,
        tone: current.tone, length: current.length, language: current.language,
        job_input: mode === "dm" ? current.jobInput : "", include_profile: current.includeProfile,
        dm_intent: current.dmIntent, modification: revision === "custom" ? current.modification : "",
        hashtags: current.hashtags && mode === "post", emoji: current.emoji,
        current_draft: revision ? current.text : "", revision,
      }, controller.signal, event => {
        if (event.type === "notice") flash(event.message || "");
        if (event.type === "status") setGenerationLabel(event.message || "Reading job…");
        if (event.type === "job") { update(mode, { job: event.job || null }); setGenerationLabel("Writing…"); }
        if (event.type === "context") update(mode, { facts: event.facts || [] });
        if (event.type === "draft_delta") { draft += event.text || ""; update(mode, { text: draft }); }
        if (event.type === "result") {
          resultSeen = true;
          update(mode, { text: event.text || "", suggestions: event.hashtags || [], facts: event.facts || [] });
        }
        if (event.type === "done") {
          if (!resultSeen) throw new Error("The companion did not return a completed draft.");
          update(mode, { phase: "complete" });
        }
      });
    } catch (cause) {
      update(mode, { phase: "incomplete" });
      if (controller.signal.aborted) flash("Generation stopped. Your partial draft is preserved.");
      else setError(cause instanceof Error ? cause.message : "Generation failed.");
    } finally {
      abort.current = null; setGenerating(false);
    }
  }
  async function copy() {
    try {
      const tags = composer.selectedTags.join(" ");
      await navigator.clipboard.writeText(composer.text.trim() + (tags ? "\n\n" + tags : ""));
      flash(composer.phase === "complete" ? "Draft copied. Review it before sending." : "Partial draft copied.");
    } catch { setError("Clipboard access failed. Select and copy the draft manually."); }
  }
  async function acceptWelcome() {
    const next = { ...settings, welcomeSeen: true };
    await saveSettings(next); setSettings(next); setWelcome(false);
  }
  const profileCount = savedProfile.facts.filter(f => f.confirmed).length;

  return <div className="app">
    <header className="header">
      <img className="brand-mark" src="icons/48.png" alt="" />
      <div className="brand"><h1>draft-kit</h1></div>
      <span className={"connection-dot " + (online && settings.token ? "connected" : "")} title={online && settings.token ? "Companion connected" : "Companion not connected"} />
    </header>
    <nav className="tabs" aria-label="Main navigation">
      {(["dm", "post", "profile", "settings"] as Tab[]).map(item =>
        <button key={item} className={tab === item ? "active" : ""} onClick={() => { setTab(item); setError(""); }} disabled={generating && item !== mode}>
          <Icon name={item} /><span>{({ dm: "DM", post: "Post", profile: "My context", settings: "Connect" })[item]}</span>
        </button>)}
    </nav>
    {notice && <div className="toast" role="status">{notice}</div>}
    {error && <div className="alert error" role="alert"><span>{error}</span><button className="dismiss" aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}
    <main>
      {(tab === "dm" || tab === "post") && <>
        <div className="section-heading">
          <h2>{mode === "dm" ? "Write a job DM" : "Write a post"}</h2>
        </div>
        {demo ? <div className="alert demo">Demo · template, not AI.</div> :
          !status?.plan_enabled && <div className="alert neutral">Connect ChatGPT to write. <button className="text-button" onClick={() => setTab("settings")}>Connect →</button></div>}
        <section className="card compose-card">
          {mode === "dm" ? <>
            <fieldset className="dm-intent" disabled={generating}>
              <legend>Message purpose</legend>
              <label className="check"><input type="radio" name="dm-intent" value="referral" checked={composer.dmIntent === "referral"} onChange={() => update(mode, { dmIntent: "referral" })} />Ask an employee for a referral</label>
              <label className="check"><input type="radio" name="dm-intent" value="hiring" checked={composer.dmIntent === "hiring"} onChange={() => update(mode, { dmIntent: "hiring" })} />Contact the hiring team</label>
            </fieldset>
            <label htmlFor="job-input">Job description or link</label>
            <textarea id="job-input" className="prompt-input" maxLength={16000} value={composer.jobInput}
              placeholder="Paste the JD or an https:// job link…"
              onChange={e => update(mode, { jobInput: e.target.value, job: null })} disabled={generating} />
            <p className="field-hint">Links are read automatically. No name needed.</p>
            {composer.job && <details className="details job-details"><summary>{composer.job.title}{composer.job.company ? " · " + composer.job.company : ""}</summary>
              {composer.job.location && <p>{composer.job.location}</p>}<a href={composer.job.url} target="_blank" rel="noreferrer">Job source ↗</a>
              {composer.job.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
              <p className="job-description">{composer.job.description}</p>
            </details>}
          </> : <>
            <label htmlFor="prompt">What do you want to share?</label>
            <textarea id="prompt" className="prompt-input" maxLength={8000} value={composer.prompt}
              placeholder="A lesson, project update or interview experience…"
              onChange={e => update(mode, { prompt: e.target.value })} disabled={generating} />
          </>}
          {mode === "post" && <fieldset className="tone-field" disabled={generating}>
            <legend>Tone {mode === "post" && <span className="required">choose one</span>}</legend>
            <div className="tone-options">{TONES.map(tone =>
              <button key={tone} type="button" aria-pressed={composer.tone === tone} className={composer.tone === tone ? "selected" : ""} onClick={() => update(mode, { tone })}>{tone}</button>)}</div>
            <details className="details custom-tone"><summary>Custom tone</summary><input aria-label="Custom tone" maxLength={80} placeholder="Describe a tone…" value={TONES.includes(composer.tone) ? "" : composer.tone} onChange={e => update(mode, { tone: e.target.value })} /></details>
          </fieldset>}
          {mode === "post" && <label className="check hashtag-switch"><input type="checkbox" checked={composer.hashtags} onChange={e => update(mode, { hashtags: e.target.checked })} disabled={generating} />Suggest hashtags</label>}
          <details className="details options"><summary>More options</summary>
          <div className="row">
            <div className="field"><label htmlFor="length">Length</label><select id="length" value={composer.length} onChange={e => update(mode, { length: e.target.value })} disabled={generating}><option value="short">Short</option><option value="medium">Medium</option><option value="long">Detailed</option></select></div>
            <div className="field"><label htmlFor="language">Language</label><input id="language" value={composer.language} maxLength={80} onChange={e => update(mode, { language: e.target.value })} disabled={generating} /></div>
          </div>
          <div className="switches">
            <label className="check"><input type="checkbox" checked={composer.includeProfile} onChange={e => update(mode, { includeProfile: e.target.checked })} disabled={generating} />Use my experience <span className="count">{profileCount} facts</span></label>
            <label className="check"><input type="checkbox" checked={composer.emoji} onChange={e => update(mode, { emoji: e.target.checked })} disabled={generating} />Allow emojis</label>
          </div>
          <div className="model-row">
            <select aria-label="Model" value={model} onChange={e => setModel(e.target.value)} disabled={!models.length || generating}>
              {!models.length && <option value="">Connect to choose a model</option>}
              {models.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
            {!demo && status?.plan_enabled && <div className="plan-note">Using ChatGPT plan · <a href="https://chatgpt.com/#settings/Usage" target="_blank" rel="noreferrer">Manage usage</a></div>}
          </div>
          </details>
          {generating ? <button className="primary generating" onClick={() => abort.current?.abort()}><span className="spinner" />{generationLabel} <span className="stop-label">Stop</span></button> :
            <button className="primary" disabled={!canGenerate || !(mode === "dm" ? composer.jobInput : composer.prompt).trim() || !composer.tone.trim()} onClick={() => void generate()}><Icon name="spark" />{demo ? "Generate demo draft" : mode === "dm" ? "Write DM" : "Write post"}</button>}
        </section>
        {composer.phase !== "empty" && <section className="card result-card">
          <div className="result-heading"><h3>Your draft</h3><span className={"phase " + composer.phase}>{composer.phase === "complete" ? demo ? "Demo" : "Ready to review" : composer.phase === "streaming" ? generationLabel : "Incomplete"}</span></div>
          <textarea aria-label="Draft" className="draft-input" value={composer.text} onChange={e => update(mode, { text: e.target.value })} readOnly={generating} maxLength={24000} />
          <div className="draft-meta"><span>{composer.text.length} characters</span><span>{composer.text.trim() ? composer.text.trim().split(/\s+/).length : 0} words</span></div>
          {composer.suggestions.length > 0 && <div className="hashtag-area"><label>Hashtags to add <span>select what fits</span></label><div className="tag-options">{composer.suggestions.map(tag =>
            <button key={tag} aria-pressed={composer.selectedTags.includes(tag)} className={composer.selectedTags.includes(tag) ? "selected" : ""} onClick={() => update(mode, { selectedTags: composer.selectedTags.includes(tag) ? composer.selectedTags.filter(t => t !== tag) : [...composer.selectedTags, tag] })}>{tag}</button>)}</div></div>}
          {composer.facts.length > 0 && <details className="details context-details"><summary>Profile context included <span>{composer.facts.length} facts</span></summary><ul>{composer.facts.map(f => <li key={f.id}>{f.text}</li>)}</ul></details>}
          <div className="modification-field">
            <label htmlFor="modification">What should change?</label>
            <textarea id="modification" maxLength={4000} value={composer.modification} placeholder="Make it shorter, highlight a relevant achievement…" onChange={e => update(mode, { modification: e.target.value })} disabled={generating} />
            <button className="secondary full" onClick={() => void generate("custom")} disabled={!canGenerate || composer.phase !== "complete" || !composer.text.trim() || !composer.modification.trim()}>Apply changes</button>
          </div>
          <div className="revisions">
            {(["shorten", "warmer", "direct", ...(mode === "post" ? ["hook"] : [])]).map(action =>
              <button key={action} disabled={generating || composer.phase !== "complete"} onClick={() => void generate(action)}>{({ shorten: "Shorten", warmer: "Warmer", direct: "More direct", hook: "New hook" } as Record<string, string>)[action]}</button>)}
            {backups[mode] && <button disabled={generating} onClick={() => {
              const previous = backups[mode];
              if (previous) {
                update(mode, previous);
                setBackups(values => ({ ...values, [mode]: undefined }));
                flash("Previous draft restored.");
              }
            }}>Restore previous draft</button>}
          </div>
          <button className="primary copy" onClick={() => void copy()} disabled={generating || !composer.text.trim()}>{composer.phase === "complete" ? "Copy draft" : "Copy partial draft"}</button>
        </section>}
      </>}
      {tab === "profile" && <>
        <div className="section-heading"><h2>Your experience</h2></div>
        <section className="card resume-import">
          <label htmlFor="resume-file">Upload résumé</label>
          <input id="resume-file" type="file" accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain" disabled={working || generating || !settings.token || !online} onChange={e => { void importResume(e.target.files?.[0]); e.target.value = ""; }} />
          <p className="field-hint">PDF, DOCX or TXT · up to 5 MB</p>
          {working && <p className="field-hint" role="status">Reading résumé…</p>}
          {profile.resume_filename && <div className="import-source"><span>{profile.resume_filename}</span></div>}
          {importWarnings.length > 0 && <details className="details"><summary>Import notes</summary><ul>{importWarnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
          {profileDirty.current && profile.facts.some(f => f.source === "resume" && !f.confirmed) && <p className="field-hint">Review and save to use these facts.</p>}
        </section>
        <section className="card">
          <label htmlFor="name">Your name</label><input id="name" placeholder="Name" value={profile.name} maxLength={120} onChange={e => editProfile({ ...profile, name: e.target.value })} />
          <label htmlFor="headline">Professional headline</label><input id="headline" placeholder="Your role · key skills · industry" value={profile.headline} maxLength={240} onChange={e => editProfile({ ...profile, headline: e.target.value })} />
          <label htmlFor="facts">Experience & achievements</label><p className="field-hint">One verified fact per line.</p>
          <textarea id="facts" className="facts-input" value={profile.facts.map(f => f.text).join("\n")} placeholder={"Your roles, responsibilities and achievements.\nA project you completed and its measurable impact."}
            onChange={e => {
              const lines = e.target.value.split("\n");
              editProfile({ ...profile, facts: lines.map((text, index) => {
                const old = profile.facts[index];
                const unchanged = old?.text === text;
                return {
                  id: old?.id || crypto.randomUUID(), text, confirmed: false,
                  source: unchanged ? old.source : "manual",
                  source_url: unchanged ? old.source_url : "",
                  source_filename: unchanged ? old.source_filename : "",
                };
              }) });
              setConfirmed(false);
            }} />
          <label htmlFor="style">How should your writing sound?</label><textarea id="style" maxLength={1200} placeholder="For example: concise and friendly; avoid corporate phrases." value={profile.writing_style} onChange={e => editProfile({ ...profile, writing_style: e.target.value })} />
          <label className="check confirmation"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />I have checked these facts and want them used in drafts.</label>
          <button className="primary" onClick={() => {
            const cleaned = { ...profile, facts: profile.facts.filter(f => f.text.trim()).map(f => ({ ...f, text: f.text.trim() })) };
            // Save from the cleaned snapshot rather than waiting for React state.
            setProfile(cleaned);
            void (async () => {
              setWorking(true); setError("");
              try {
                if (cleaned.facts.length && !confirmed) throw new Error("Check and confirm your facts before saving.");
                const approved = { ...cleaned, facts: cleaned.facts.map(f => ({ ...f, confirmed: true })) };
                const saved = await request<Profile>(settings, "/profile", approved, "PUT");
                profileDirty.current = false;
                setProfile(saved); setSavedProfile(saved); flash("Your professional context is saved.");
              } catch (cause) { setError(cause instanceof Error ? cause.message : "Saving failed."); }
              finally { setWorking(false); }
            })();
          }} disabled={working || !settings.token || !online}>Save my context</button>
          <div className="profile-actions"><button onClick={exportProfile} disabled={!savedProfile.facts.length}>Export</button><label className="import-button">Import<input type="file" accept=".json,application/json" onChange={e => { void importProfile(e.target.files?.[0]); e.target.value = ""; }} /></label><button className="danger" onClick={() => void clearProfile()} disabled={working || !settings.token}>Clear saved profile</button></div>
          <details className="details"><summary>Try a sample profile</summary><p className="field-hint">A fictional profile for exploring the interface.</p><button className="secondary" onClick={() => { editProfile(SAMPLE); setConfirmed(false); flash("Sample loaded. Review it before saving."); }}>Load fictional sample</button></details>
        </section>
        <div className="privacy-note"><Icon name="profile" /><p>Saved locally. Relevant facts go to OpenAI for live drafts.</p></div>
      </>}
      {tab === "settings" && <>
        <div className="section-heading"><h2>Connect</h2></div>
        <section className="card">
          <div className="step-label"><span>1</span><h3>Pair your local companion</h3></div>
          <p className="field-hint">Start the companion. Paste its pairing code here.</p>
          <label htmlFor="address">Companion address</label><input id="address" value={address} onChange={e => setAddress(e.target.value)} placeholder="http://127.0.0.1:1455" spellCheck={false} />
          <label htmlFor="pair-code">Pairing code</label><input id="pair-code" value={pairCode} onChange={e => setPairCode(e.target.value)} placeholder="Paste the code from your terminal" spellCheck={false} autoComplete="off" />
          <button className="secondary full" onClick={() => void pair()} disabled={working || !pairCode.trim()}>{working ? "Connecting…" : settings.token ? "Pair again" : "Pair companion"}</button>
          <div className="connection-line"><span className={"connection-dot " + (online && settings.token ? "connected" : "")} />{online && settings.token ? "Paired and reachable" : online ? "Companion found · pairing needed" : "Companion not reachable"}<button className="text-button" disabled={working} onClick={() => void refresh()}>Check connection</button></div>
        </section>
        <section className="card">
          <div className="step-label"><span>2</span><h3>Connect ChatGPT</h3></div>
          {demo ? <><div className="alert demo">Demo · no AI requests.</div><p className="field-hint">Restart without --demo to connect ChatGPT.</p><button className="secondary full" onClick={() => setTab("dm")} disabled={!settings.token}>Try the demo</button></> :
            <>
              <p className="field-hint">Uses your eligible ChatGPT plan allowance.</p>
              {status?.connected && <div className="account"><div className="avatar">{(status.email || "C")[0].toUpperCase()}</div><div><strong>{status.email || "ChatGPT account"}</strong><span>{status.plan_enabled ? "Plan usage connected" : "Plan permission needed"}</span></div></div>}
              <button className="chatgpt-button full" onClick={() => void signIn()} disabled={!settings.token || !online || working || status?.pending}>{status?.pending ? "Finish sign-in in your browser…" : status?.connected ? "Reconnect with ChatGPT" : "Continue with ChatGPT"}</button>
              {status?.pending && <p className="footnote">Waiting for sign-in. Return here when the browser says Connected.</p>}
              <div className="settings-links"><a href="https://chatgpt.com/#settings/Usage" target="_blank" rel="noreferrer">Manage usage ↗</a>{status?.connected && <button className="text-button danger" onClick={() => void disconnect()} disabled={working}>Disconnect</button>}</div>
            </>}
        </section>
        <p className="footnote">v{installedVersion} · Personal prototype · <a href="https://developers.openai.com/siwc/token-sharing-open-source" target="_blank" rel="noreferrer">Connection documentation</a></p>
      </>}
    </main>
    {welcome && <div className="modal-backdrop"><section className="welcome-modal" role="dialog" aria-modal="true" aria-labelledby="welcome-title"><img className="brand-mark" src="icons/48.png" alt="" /><h2 id="welcome-title">You're using your ChatGPT plan.</h2><p>Eligible AI requests in draft-kit use your ChatGPT plan or available credits. You can manage usage and app access in ChatGPT settings.</p><a href="https://chatgpt.com/#settings/Usage" target="_blank" rel="noreferrer">Manage usage ↗</a><button className="primary" onClick={() => void acceptWelcome()}>Got it</button></section></div>}
    {!loaded && <div className="loading-overlay" role="status">Opening your workspace…</div>}
  </div>;
}

createRoot(document.getElementById("root")!).render(<App />);
