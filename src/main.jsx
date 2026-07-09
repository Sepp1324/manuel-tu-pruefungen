import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  BarChart3,
  BookOpenCheck,
  Check,
  ClipboardList,
  Edit3,
  Flame,
  ImagePlus,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Target,
  Trophy,
  X,
} from "lucide-react";
import "./styles.css";

const RATING_LABELS = { 1: "Nochmal", 2: "Schwer", 3: "Gut", 4: "Leicht" };
const TRIAGE_REASONS = [
  ["kein_kontext", "Kein Kontext"],
  ["person_firma", "Person/Firma"],
  ["vorlesungsinfo", "Vorlesungsinfo"],
  ["zu_spezifisch", "Zu spezifisch"],
  ["unverstaendlich", "Unverstaendlich"],
  ["falsch_extrahiert", "Falsch extrahiert"],
];
const REVIEW_REASONS = [
  ["begriff_nicht_gewusst", "Begriff nicht gewusst"],
  ["prozess_verwechselt", "Prozess verwechselt"],
  ["frage_unklar", "Frage unklar"],
  ["karte_schlecht", "Karte schlecht"],
];
const CARD_REPORT_REASONS = [
  ["english_noise", "Englisch"],
  ["falsche_antwort", "Falsch"],
  ["nonsense", "Nonsense"],
  ["kein_kontext", "Kein Kontext"],
  ["foto_empfohlen", "Foto/Skizze fehlt"],
  ["karte_schlecht", "Karte schlecht"],
];
const EXAM_ERROR_TYPES = [
  ["definition", "Definition fehlt"],
  ["process", "Prozessschritte vertauscht"],
  ["conditions", "Bedingungen fehlen"],
  ["formula", "Formel/Reaktion fehlt"],
  ["example", "Beispiel fehlt"],
];
const CONFIDENCE_LEVELS = [
  ["sure", "sicher"],
  ["unsure", "unsicher"],
];
const EXAM_REASONS = [
  ...EXAM_ERROR_TYPES.map(([key, label]) => [`exam_${key}`, label]),
  ["exam_confidence_trap", "Sicher, aber falsch"],
];
const QUALITY_REASONS = [
  ["foto_empfohlen", "Foto empfohlen"],
  ["wiederholt_schwach", "Wiederholt schwach"],
  ["pruefung_miss", "Pruefung nicht gewusst"],
  ["archiv_partial", "Archiv teilweise"],
  ["archiv_miss", "Archiv nicht gewusst"],
  ["auto_improved", "Automatisch verbessert"],
  ["english_noise", "Englisch"],
  ["falsche_antwort", "Falsche Antwort"],
  ["nonsense", "Nonsense"],
  ["seed_auto_suspension_restored", "Auto-Reaktivierung"],
];
const ALL_REASONS = [...TRIAGE_REASONS, ...REVIEW_REASONS, ...EXAM_REASONS, ...QUALITY_REASONS];
const EXAM_EVALS = [
  ["full", "voll"],
  ["partial", "teilweise"],
  ["miss", "nicht gewusst"],
];
const WORKSHOP_ISSUE_LABELS = {
  english: "Englisch",
  long: "Zu lang",
  missing_context: "Kein Kontext",
  photo: "Foto empfohlen",
  sketch: "Skizze",
  formula: "Formel-Fix",
  extracted: "Extraktion",
  person_company: "Person/Firma",
  lecture_info: "Vorlesungsinfo",
  duplicate: "Duplikat",
  nonsense: "Nonsense",
};
const FORMULA_TOOLBAR_ITEMS = [
  ["H2SO4", "H<sub>2</sub>SO<sub>4</sub>"],
  ["H2O", "H<sub>2</sub>O"],
  ["SO2", "SO<sub>2</sub>"],
  ["SO3", "SO<sub>3</sub>"],
  ["Na2SO4", "Na<sub>2</sub>SO<sub>4</sub>"],
  ["CaCO3", "CaCO<sub>3</sub>"],
  ["NH3", "NH<sub>3</sub>"],
  ["2-", "<sup>2-</sup>"],
  ["+", "<sup>+</sup>"],
  ["->", " &rarr; "],
  ["<=>", " &harr; "],
];
const EXAM_CHECKLIST = [
  ["definition", "Definition"],
  ["process", "Prozess/Aufbau"],
  ["conditions", "Bedingungen"],
  ["formula", "Formel/Reaktion"],
  ["example", "Beispiel/Zweck"],
];

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let message = await res.text();
    try {
      message = JSON.parse(message).detail || message;
    } catch {
      // keep raw response
    }
    if (res.status === 401 && message === "nicht angemeldet") window.location.href = "/login";
    throw new Error(message);
  }
  return res.json();
}

function appendHtml(value = "", html = "") {
  return [value.trimEnd(), html].filter(Boolean).join("\n\n");
}

function appendInline(value = "", html = "") {
  const trimmed = value.trimEnd();
  return `${trimmed}${trimmed ? " " : ""}${html}`;
}

function insertHtmlAt(value = "", html = "", start = value.length, end = start) {
  const before = value.slice(0, start).trimEnd();
  const after = value.slice(end).trimStart();
  return [before, html, after].filter(Boolean).join("\n\n");
}

async function uploadPhoto(file) {
  const body = new FormData();
  body.append("file", file);
  const res = await fetch("/api/uploads/photo", { method: "POST", body });
  if (!res.ok) {
    let message = await res.text();
    try {
      message = JSON.parse(message).detail || message;
    } catch {
      // keep raw response
    }
    if (res.status === 401 && message === "nicht angemeldet") window.location.href = "/login";
    throw new Error(message);
  }
  return res.json();
}

function PhotoTextarea({ value = "", onValue, rows = 6, ...props }) {
  const ref = useRef(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function paste(e) {
    const items = Array.from(e.clipboardData?.items || []);
    const files = items
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (!files.length) return;
    e.preventDefault();
    setBusy(true);
    setMsg("");
    try {
      const textarea = ref.current;
      const start = textarea?.selectionStart ?? value.length;
      const end = textarea?.selectionEnd ?? start;
      let next = value;
      let cursor = start;
      for (const file of files) {
        const uploaded = await uploadPhoto(file);
        next = insertHtmlAt(next, uploaded.html, cursor, cursor === start ? end : cursor);
        cursor = next.length;
      }
      onValue?.(next);
      setMsg(files.length === 1 ? "Foto eingefuegt" : `${files.length} Fotos eingefuegt`);
    } catch (err) {
      setMsg(err.message || "Einfuegen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <textarea
        {...props}
        ref={ref}
        rows={rows}
        value={value}
        onChange={(e) => onValue?.(e.target.value)}
        onPaste={paste}
      />
      {(busy || msg) && <small className="paste-status">{busy ? "Fuege Foto ein..." : msg}</small>}
    </>
  );
}

function FormulaToolbar({ value = "", onValue }) {
  return (
    <div className="formula-toolbar" aria-label="Formelbausteine">
      {FORMULA_TOOLBAR_ITEMS.map(([label, html]) => (
        <button key={label} type="button" onClick={() => onValue?.(appendInline(value, html))}>
          <span dangerouslySetInnerHTML={{ __html: html.trim() || label }} />
        </button>
      ))}
    </div>
  );
}

function PhotoButton({ onInsert, label = "Foto" }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  async function change(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    setMsg("");
    try {
      const uploaded = await uploadPhoto(file);
      onInsert?.(uploaded.html);
      setMsg("eingefuegt");
    } catch (err) {
      setMsg(err.message || "Upload fehlgeschlagen");
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }
  return (
    <span className="photo-upload">
      <label className={`photo-upload-button ${busy ? "busy" : ""}`}>
        <ImagePlus size={16} />
        {busy ? "Laedt..." : label}
        <input type="file" accept="image/*" onChange={change} />
      </label>
      {msg && <small>{msg}</small>}
    </span>
  );
}

function VisualHtmlField({ label, value = "", onValue, photoLabel = "Foto", minHeight = 120 }) {
  const ref = useRef(null);
  const [pasteMsg, setPasteMsg] = useState("");

  useEffect(() => {
    if (!ref.current || document.activeElement === ref.current) return;
    if ((ref.current.innerHTML || "") !== (value || "")) {
      ref.current.innerHTML = value || "";
    }
  }, [value]);

  function sync() {
    onValue?.(ref.current?.innerHTML || "");
  }

  function command(cmd, arg = null) {
    ref.current?.focus();
    document.execCommand(cmd, false, arg);
    sync();
  }

  function insertHtml(html) {
    ref.current?.focus();
    document.execCommand("insertHTML", false, html);
    sync();
  }

  async function paste(e) {
    const files = Array.from(e.clipboardData?.items || [])
      .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
      .map((item) => item.getAsFile())
      .filter(Boolean);
    if (!files.length) return;
    e.preventDefault();
    setPasteMsg("Fuege Foto ein...");
    try {
      for (const file of files) {
        const uploaded = await uploadPhoto(file);
        insertHtml(uploaded.html);
      }
      setPasteMsg(files.length === 1 ? "Foto eingefuegt" : `${files.length} Fotos eingefuegt`);
    } catch (err) {
      setPasteMsg(err.message || "Einfuegen fehlgeschlagen");
    }
  }

  return (
    <div className="visual-field">
      <div className="visual-field-head">
        <b>{label}</b>
        <span>direkt in der Vorschau bearbeiten</span>
      </div>
      <div className="visual-toolbar">
        <button type="button" onMouseDown={(e) => { e.preventDefault(); command("bold"); }}><b>B</b></button>
        <button type="button" onMouseDown={(e) => { e.preventDefault(); command("insertUnorderedList"); }}>Liste</button>
        <button type="button" onMouseDown={(e) => { e.preventDefault(); command("formatBlock", "p"); }}>Absatz</button>
        <button type="button" onMouseDown={(e) => { e.preventDefault(); command("removeFormat"); }}>Format weg</button>
        {FORMULA_TOOLBAR_ITEMS.map(([labelText, html]) => (
          <button key={labelText} type="button" onMouseDown={(e) => { e.preventDefault(); insertHtml(html); }}>
            <span dangerouslySetInnerHTML={{ __html: html.trim() || labelText }} />
          </button>
        ))}
        <PhotoButton label={photoLabel} onInsert={insertHtml} />
      </div>
      <div
        ref={ref}
        className="visual-html-editor"
        contentEditable
        suppressContentEditableWarning
        style={{ minHeight }}
        data-placeholder="Hier direkt in die gerenderte Karte schreiben..."
        onInput={sync}
        onBlur={sync}
        onPaste={paste}
      />
      {pasteMsg && <small className="paste-status">{pasteMsg}</small>}
      <details className="raw-html-details">
        <summary>HTML bearbeiten</summary>
        <PhotoTextarea value={value || ""} onValue={onValue} rows={5} />
      </details>
    </div>
  );
}

function EditableCardPreview({ question = "", answer = "", onQuestion, onAnswer }) {
  return (
    <div className="editable-card-preview">
      <VisualHtmlField
        label="Frage"
        value={question}
        onValue={onQuestion}
        photoLabel="Foto in Frage"
        minHeight={110}
      />
      <VisualHtmlField
        label="Antwort"
        value={answer}
        onValue={onAnswer}
        photoLabel="Foto in Antwort"
        minHeight={180}
      />
    </div>
  );
}

function CardRenderPreview({ question = "", answer = "" }) {
  if (!question.trim() && !answer.trim()) return null;
  return (
    <div className="card-render-preview">
      <div>
        <b>Frage Vorschau</b>
        <div className="preview-html" dangerouslySetInnerHTML={{ __html: question || "<span>Leer</span>" }} />
      </div>
      <div>
        <b>Antwort Vorschau</b>
        <div className="preview-html" dangerouslySetInnerHTML={{ __html: answer || "<span>Leer</span>" }} />
      </div>
    </div>
  );
}

function PhotoLightbox({ photo, onClose }) {
  useEffect(() => {
    if (!photo) return undefined;
    function onKey(e) {
      if (e.key === "Escape") onClose?.();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [photo, onClose]);
  if (!photo) return null;
  return (
    <div className="photo-lightbox" onClick={onClose}>
      <button title="Schliessen" onClick={onClose}><X size={18} /></button>
      <img src={photo.src} alt={photo.alt || "Foto"} onClick={(e) => e.stopPropagation()} />
      {photo.alt && <span>{photo.alt}</span>}
    </div>
  );
}

function pct(n, d) {
  return d ? Math.round((n / d) * 100) : 0;
}

function formatDate(s) {
  if (!s) return "neu";
  const d = new Date(s);
  return `${d.toLocaleDateString("de-AT")} ${d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}`;
}

function formatBytes(n = 0) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

const ANSWER_STOPWORDS = new Set([
  "der", "die", "das", "und", "oder", "mit", "von", "zur", "zum", "eine", "einer", "eines", "ist", "sind",
  "werden", "wird", "fuer", "fur", "bei", "als", "auf", "aus", "dem", "den", "des", "durch", "nicht",
  "definition", "prozess", "struktur", "bedingungen", "beispiel", "quelle", "kontext", "antwort",
]);

function stripHtmlText(value = "") {
  return value
    .replace(/<br\s*\/?>/gi, " ")
    .replace(/<[^>]*>/g, " ")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function importantTerms(value = "", limit = 16) {
  const counts = {};
  stripHtmlText(value)
    .toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss")
    .match(/[a-z0-9]{4,}/g)?.forEach((token) => {
      if (ANSWER_STOPWORDS.has(token)) return;
      counts[token] = (counts[token] || 0) + 1;
    });
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length)
    .slice(0, limit)
    .map(([term]) => term);
}

function answerComparison(answer = "", question = {}) {
  const source = [
    question.answer || "",
    ...(question.scaffold || []),
    ...(question.rubric || []).map((item) => `${item.category || ""} ${item.prompt || ""}`),
  ].join(" ");
  const terms = importantTerms(source, 18);
  const answerText = stripHtmlText(answer).toLowerCase()
    .replace(/ä/g, "ae").replace(/ö/g, "oe").replace(/ü/g, "ue").replace(/ß/g, "ss");
  const hits = terms.filter((term) => answerText.includes(term));
  const missing = terms.filter((term) => !answerText.includes(term));
  return {
    terms,
    hits,
    missing,
    score: terms.length ? Math.round((hits.length / terms.length) * 100) : 0,
  };
}

function reasonLabel(reason) {
  return ALL_REASONS.find(([key]) => key === reason)?.[1] || reason || "Ohne Grund";
}

function issueLabel(issue) {
  return WORKSHOP_ISSUE_LABELS[issue] || issue || "Hinweis";
}

function formatSeconds(s) {
  const safe = Math.max(0, Math.floor(s || 0));
  const h = Math.floor(safe / 3600);
  const m = Math.floor((safe % 3600) / 60);
  const sec = safe % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}` : `${m}:${String(sec).padStart(2, "0")}`;
}

function AuthBar() {
  const [user, setUser] = useState("");
  useEffect(() => {
    api("/api/auth/me").then((j) => setUser(j.username || "")).catch(() => {});
  }, []);
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" }).catch(() => {});
    window.location.href = "/login";
  }
  return (
    <div className="authbar">
      <span>{user}</span>
      <button title="Abmelden" onClick={logout}><LogOut size={15} /></button>
    </div>
  );
}

function Login() {
  const [username, setUsername] = useState("manuel");
  const [password, setPassword] = useState("");
  const [msg, setMsg] = useState("");
  async function submit(e) {
    e.preventDefault();
    setMsg("");
    try {
      await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      window.location.href = "/";
    } catch (err) {
      setMsg(err.message || "Login fehlgeschlagen");
    }
  }
  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={submit}>
        <div className="brand-mark">TU</div>
        <h1>TU Chemie SR-Trainer</h1>
        <p>Chemische Technologien organischer Stoffe, fokussiert auf Manuels Pruefung am 21.09.</p>
        <label>
          Benutzer
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" />
        </label>
        <label>
          Passwort
          <input value={password} onChange={(e) => setPassword(e.target.value)} type="password" autoComplete="current-password" autoFocus />
        </label>
        <button className="primary">Einloggen</button>
        {msg && <div className="form-msg bad">{msg}</div>}
      </form>
    </main>
  );
}

function Stat({ label, value, tone = "" }) {
  return (
    <div className="stat">
      <div className={`n ${tone}`}>{value}</div>
      <div className="l">{label}</div>
    </div>
  );
}

function XpCard({ xp, streak }) {
  const p = {
    rank: "Labor-Starter",
    level: 1,
    total_xp: 0,
    progress_pct: 0,
    xp_in_level: 0,
    next_level_xp: 350,
    xp_to_next: 350,
    today_xp: 0,
    ...(xp || {}),
  };
  return (
    <section className="xp-card">
      <div className="xp-head">
        <Trophy size={22} />
        <div>
          <h2>{p.rank}</h2>
          <p>Level {p.level} · {p.total_xp} XP · heute +{p.today_xp}</p>
        </div>
      </div>
      <div className="xp-meter"><span style={{ width: `${p.progress_pct}%` }} /></div>
      <div className="xp-meta">
        <span>{p.xp_in_level}/{p.next_level_xp} XP</span>
        <span>{p.xp_to_next} bis Level {p.level + 1}</span>
        <span><Flame size={13} /> {streak?.current || 0} Tage Serie</span>
      </div>
    </section>
  );
}

function StudyPlan({ plan, startSession }) {
  if (!plan) return null;
  return (
    <section className="panel plan-panel">
      <div>
        <h2>{plan.title}</h2>
        <p>{plan.message}</p>
      </div>
      <div className="plan-metrics">
        <span><b>{plan.daily_cards || 0}</b> Karten/Tag</span>
        <span><b>{plan.new_cards_today}</b> neue Karten</span>
        <span><b>{plan.reviews_today}</b> Wiederholungen</span>
        <span><b>{plan.mini_exams_per_week || 0}</b> Mini-Pruefungen/Woche</span>
        <span><b>{plan.open_cards}</b> offen</span>
      </div>
      <div className="focus-strip">
        {(plan.focus || []).map((ch) => (
          <button key={ch.kap} onClick={() => startSession?.("anki", ch.kap)}>
            VO{ch.kap} · Score {ch.weak_score}
          </button>
        ))}
      </div>
    </section>
  );
}

function TodayPlan({ plan, setRoute, startSession }) {
  if (!plan) return null;
  const workload = plan.workload || {};
  function runTask(task) {
    if (task.key === "due" || task.key === "new") startSession?.("anki");
    else if (task.key === "photo") startSession?.("photos");
    else setRoute?.(task.route || "home");
  }
  return (
    <section className="panel today-plan">
      <div className="section-head">
        <div>
          <h2>Heute solltest du machen</h2>
          <p>{plan.message}</p>
        </div>
        <span className="deck-pill">{plan.days_left} Tage</span>
      </div>
      <div className="plan-metrics">
        <span><b>{workload.daily_cards || 0}</b> Karten heute</span>
        <span><b>{workload.backlog_per_day || 0}</b> pro Tag offen</span>
        <span><b>{workload.repair_cards || 0}</b> Werkstattkarten</span>
        <span><b>{workload.photo_cards || 0}</b> Foto-Queue</span>
      </div>
      <div className="today-task-grid">
        {(plan.tasks || []).filter((task) => task.amount !== 0).map((task) => (
          <button
            key={task.key}
            onClick={() => runTask(task)}
          >
            <b>{task.amount}</b>
            <span>{task.label}</span>
            <em>{task.detail}</em>
          </button>
        ))}
      </div>
      {!!plan.focus?.length && (
        <div className="focus-strip">
          {plan.focus.map((ch) => (
            <button key={ch.kap} onClick={() => startSession?.("anki", ch.kap)}>
              VO{ch.kap} · {ch.name}
            </button>
          ))}
        </div>
      )}
    </section>
  );
}

function WeaknessHeatmap({ items = [], startSession }) {
  const max = Math.max(1, ...items.map((x) => x.weak_score || 0));
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Schwaechen-Heatmap</h2>
          <p>Gewichtet aus Abdeckung, Faelligkeit, Fehlern und Trefferquote.</p>
        </div>
      </div>
      <div className="heatmap">
        {items.map((ch) => (
          <button key={ch.kap} onClick={() => startSession?.("anki", ch.kap)}>
            <span>VO{ch.kap}</span>
            <b>{ch.name}</b>
            <i style={{ width: `${Math.max(6, (ch.weak_score / max) * 100)}%` }} />
            <em>{ch.progress}% gesehen · {ch.hit_rate == null ? "-" : `${ch.hit_rate}%`} Quote · {ch.again} Nochmal</em>
          </button>
        ))}
      </div>
    </section>
  );
}

function TagPanel({ tags = [], onPick }) {
  if (!tags.length) return null;
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2>Themen-Tags</h2>
          <p>Schneller Einstieg in fachliche Schwaechen statt nur VO-weise zu lernen.</p>
        </div>
        <Tag size={22} />
      </div>
      <div className="tag-cloud">
        {tags.slice(0, 14).map((t) => (
          <button key={t.tag} onClick={() => onPick?.(t.tag)}>
            <b>{t.tag}</b>
            <span>{t.total} Karten</span>
          </button>
        ))}
      </div>
    </section>
  );
}

function AnswerContent({ html = "" }) {
  const plain = html.replace(/<[^>]*>/g, " ");
  const hasProcess = plain.includes("->") || plain.includes("→");
  if (!hasProcess) return <div className="answer" dangerouslySetInnerHTML={{ __html: html }} />;
  const normalized = plain.replaceAll("→", "->");
  const parts = normalized.split("->").map((p) => p.trim()).filter(Boolean).slice(0, 5);
  return (
    <div className="answer">
      <div dangerouslySetInnerHTML={{ __html: html }} />
      {parts.length > 1 && (
        <div className="process-chain">
          {parts.map((p, i) => <span key={`${p}-${i}`}>{p}</span>)}
        </div>
      )}
    </div>
  );
}

function QuestionContent({ html = "" }) {
  const marker = "\n\n";
  if (html.startsWith("Kontext:") && html.includes(marker)) {
    const [context, ...rest] = html.split(marker);
    return (
      <>
        <div className="question-context" dangerouslySetInnerHTML={{ __html: context }} />
        <h2 dangerouslySetInnerHTML={{ __html: rest.join(marker) }} />
      </>
    );
  }
  return <h2 dangerouslySetInnerHTML={{ __html: html }} />;
}

function ModuleSwitch({ modules = {}, active, onChange }) {
  const entries = Object.entries(modules);
  if (entries.length <= 1) return null;
  return (
    <div className="module-switch">
      {entries.map(([key, mod]) => (
        <button key={key} className={active === key ? "active" : ""} onClick={() => onChange(key)}>
          {mod.title || mod.full_title || key}
        </button>
      ))}
    </div>
  );
}

function Home({ data, startSession, setRoute, refresh, module, setModule }) {
  const st = data.anki || {};
  const goal = data.daily_goal || {};
  const forecast = data.forecast || {};
  return (
    <>
      <ModuleSwitch modules={data.modules || {}} active={module} onChange={setModule} />
      <section className="hero">
        <div className="days">{data.days_until_exam}</div>
        <div>
          <span className="hero-kicker">Technische Universität · Prüfungsvorbereitung</span>
          <h1>{data.title}</h1>
          <p>Manuels Anki-Style Trainer bis zur Pruefung am 21.09.2026.</p>
          <div className="hero-actions">
            <button className="primary" onClick={() => startSession("anki")}>Session starten</button>
            <button onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
            <button onClick={() => setRoute("workshop")}><Edit3 size={16} /> Werkstatt</button>
          </div>
        </div>
      </section>

      <XpCard xp={data.xp} streak={data.streak} />
      <StudyPlan plan={data.study_plan} startSession={startSession} />
      <TodayPlan plan={data.today_plan} setRoute={setRoute} startSession={startSession} />

      <section className={`day-card ${goal.status || ""}`}>
        <div>
          <h2>{goal.label}</h2>
          <p>{goal.message}</p>
        </div>
        <div className="goal-ring">{goal.progress_pct || 0}%</div>
        <div className="day-plan">
          <span><b>{goal.completed || 0}</b> erledigt</span>
          <span><b>{goal.remaining || 0}</b> offen</span>
          <span><b>{goal.target || 0}</b> Ziel</span>
        </div>
      </section>

      <WeaknessHeatmap items={(data.weaknesses || []).slice(0, 6)} startSession={startSession} />
      <TagPanel tags={data.tags || []} onPick={() => setRoute("triage")} />

      <section className="deck wide">
        <div className="deck-head">
          <div>
            <h2>Anki-Karten</h2>
            <p>{st.total || 0} Karten aus den Skripten. Keine MC-Fragen.</p>
          </div>
          <div className="button-row-inline">
            <button className="primary" disabled={!((st.due || 0) + (st.new || 0))} onClick={() => startSession("anki")}>Lernen</button>
            <button onClick={() => setRoute("exam")}><Target size={16} /> Pruefungsmodus</button>
          </div>
        </div>
        <div className="stats">
          <Stat label="faellig" value={st.due || 0} tone="bad" />
          <Stat label="neu" value={st.new || 0} tone="blue" />
          <Stat label="gesehen" value={`${st.seen || 0}/${st.total || 0}`} />
          <Stat label="Quote" value={st.hit_rate == null ? "-" : `${st.hit_rate}%`} tone="good" />
        </div>
      </section>

      <section className="panel forecast">
        <div>
          <h2>Prognose</h2>
          <p>{forecast.summary}</p>
        </div>
        <div className={`forecast-score ${forecast.band || ""}`}>
          <b>{forecast.label || "0-0%"}</b>
          <span>{forecast.band || "Start"}</span>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Fokuskapitel</h2>
            <p>Automatisch nach Fortschritt und faelligen Karten sortiert.</p>
          </div>
          <button onClick={refresh}><RefreshCw size={16} /></button>
        </div>
        <div className="chapter-grid">
          {(goal.focus_chapters || []).map((ch) => (
            <button key={ch.kap} className="chapter-card" onClick={() => startSession("anki", ch.kap)}>
              <span>VO{ch.kap}</span>
              <b>{ch.name}</b>
              <em>{ch.progress}% gesehen · {ch.due} faellig</em>
            </button>
          ))}
        </div>
      </section>
    </>
  );
}

function Study({ session, setSession, finish }) {
  const cards = session.cards || [];
  const card = cards[session.idx];
  const [revealed, setRevealed] = useState(false);
  const [preview, setPreview] = useState({});
  const [feedbackReason, setFeedbackReason] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState({ q: "", a: "", review_note: "" });
  const [editMsg, setEditMsg] = useState("");
  const [reportMsg, setReportMsg] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [secondsLeft, setSecondsLeft] = useState((session.minutes || 0) * 60);
  const progress = pct(session.idx, Math.max(cards.length, 1));
  const isExam = session.deck === "exam";
  const isTimedExam = isExam && Number(session.minutes || 0) > 0;

  useEffect(() => {
    setRevealed(false);
    setPreview({});
    setFeedbackReason("");
    setEditing(false);
    setEditMsg("");
    setReportMsg("");
    setSavingEdit(false);
    setDraft({ q: card?.q || "", a: card?.a || "", review_note: card?.review_note || "" });
  }, [card?.id]);

  useEffect(() => {
    setSecondsLeft((session.minutes || 0) * 60);
  }, [session.startedAt, session.minutes]);

  useEffect(() => {
    if (revealed && card?.id) api(`/api/preview/${encodeURIComponent(card.id)}`).then(setPreview).catch(() => {});
  }, [revealed, card?.id]);

  useEffect(() => {
    if (!isTimedExam || session.done) return undefined;
    const timer = setInterval(() => {
      setSecondsLeft((left) => {
        if (left <= 1) {
          setSession((old) => old?.done ? old : {
            ...old,
            done: true,
            timedOut: true,
            elapsedSeconds: (old.minutes || 0) * 60,
          });
          return 0;
        }
        return left - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [isTimedExam, session.done, setSession]);

  async function rate(rating) {
    const reviewReason = rating === 1 ? (feedbackReason || "begriff_nicht_gewusst") : "";
    await api("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_id: card.id,
        rating,
        source: isExam ? "exam" : "review",
        feedback_reason: reviewReason,
      }),
    });
    const nextResult = { card_id: card.id, rating, kap: card.kap, subname: card.subname, feedback_reason: reviewReason };
    if (session.idx + 1 >= cards.length) {
      const elapsedSeconds = isTimedExam ? Math.max(0, (session.minutes || 0) * 60 - secondsLeft) : undefined;
      setSession((old) => ({ ...old, done: true, elapsedSeconds, results: [...(old.results || []), nextResult] }));
    } else {
      setSession((old) => ({ ...old, idx: old.idx + 1, results: [...(old.results || []), nextResult] }));
    }
  }

  function startEdit() {
    if (!card) return;
    setDraft({ q: card.q || "", a: card.a || "", review_note: card.review_note || "" });
    setEditMsg("");
    setEditing(true);
  }

  async function saveEdit(nextStatus = card?.status || "active") {
    if (!card) return;
    setSavingEdit(true);
    setEditMsg("");
    try {
      const res = await api(`/api/cards/${encodeURIComponent(card.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          q: draft.q,
          a: draft.a,
          status: nextStatus,
          review_note: draft.review_note || "",
        }),
      });
      const updated = res.card;
      setSession((old) => ({
        ...old,
        cards: (old.cards || []).map((item) => item.id === updated.id ? { ...item, ...updated } : item),
      }));
      setDraft({ q: updated.q || "", a: updated.a || "", review_note: updated.review_note || "" });
      setEditing(false);
      setEditMsg("Karte gespeichert.");
      api(`/api/preview/${encodeURIComponent(updated.id)}`).then(setPreview).catch(() => {});
    } catch (err) {
      setEditMsg(err.message || "Speichern fehlgeschlagen");
    } finally {
      setSavingEdit(false);
    }
  }

  async function summarizeEdit() {
    if (!card) return;
    setSavingEdit(true);
    setEditMsg("");
    try {
      const res = await api(`/api/cards/${encodeURIComponent(card.id)}/summarize`, { method: "POST" });
      const updated = res.card;
      setSession((old) => ({
        ...old,
        cards: (old.cards || []).map((item) => item.id === updated.id ? { ...item, ...updated } : item),
      }));
      setDraft({ q: updated.q || "", a: updated.a || "", review_note: updated.review_note || "" });
      setEditing(true);
      setEditMsg("Karte gekuerzt. Bitte kurz pruefen und speichern oder weiterlernen.");
      api(`/api/preview/${encodeURIComponent(updated.id)}`).then(setPreview).catch(() => {});
    } catch (err) {
      setEditMsg(err.message || "Kuerzen fehlgeschlagen");
    } finally {
      setSavingEdit(false);
    }
  }

  async function markForWorkshop(reason = feedbackReason || "karte_schlecht") {
    if (!card) return;
    setSavingEdit(true);
    setEditMsg("");
    setReportMsg("");
    try {
      const note = `Lernsession: ${reasonLabel(reason)}`;
      const res = await api(`/api/cards/${encodeURIComponent(card.id)}/triage`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action: "needs_review",
          q: card.q,
          a: card.a,
          reason,
          review_note: [card.review_note || "", note].filter(Boolean).join("\n"),
        }),
      });
      setSession((old) => ({
        ...old,
        cards: (old.cards || []).map((item) => item.id === res.card.id ? { ...item, ...res.card } : item),
      }));
      setEditMsg("Karte liegt in der Werkstatt.");
      setReportMsg(`${reasonLabel(reason)} gemeldet`);
    } catch (err) {
      setEditMsg(err.message || "Markieren fehlgeschlagen");
    } finally {
      setSavingEdit(false);
    }
  }

  if (session.done) {
    const results = session.results || [];
    const attempted = results.length;
    const remaining = Math.max(cards.length - attempted, 0);
    const strong = results.filter((r) => r.rating >= 3).length;
    const cardMap = Object.fromEntries(cards.map((item) => [item.id, item]));
    const weak = results.filter((r) => r.rating <= 2).map((r) => ({ ...r, card: cardMap[r.card_id] })).slice(0, 6);
    const byKap = results.reduce((acc, r) => {
      const key = `VO${r.kap}`;
      acc[key] = acc[key] || { total: 0, ok: 0 };
      acc[key].total += 1;
      if (r.rating >= 3) acc[key].ok += 1;
      return acc;
    }, {});
    const tomorrow = Object.entries(byKap)
      .filter(([, v]) => v.ok < v.total)
      .sort((a, b) => (a[1].ok / a[1].total) - (b[1].ok / b[1].total))
      .slice(0, 3);
    return (
      <section className="done exam-result session-debrief">
        <Check size={32} />
        <h2>{isExam ? "Pruefungsmodus abgeschlossen" : "Tagesabschluss"}</h2>
        <p>
          {session.timedOut ? "Zeit abgelaufen. " : ""}
          {attempted ? `${strong} von ${attempted} Karten sicher erinnert.` : "Noch keine Karte bewertet."}
          {" "}
          {remaining ? `${remaining} Karte(n) offen geblieben.` : weak.length ? `${weak.length} Karte(n) gehen in den Fokus.` : "Keine harte Schwachstelle in dieser Runde."}
        </p>
        {isTimedExam && <p className="muted">Dauer: {formatSeconds(session.elapsedSeconds ?? ((session.minutes || 0) * 60 - secondsLeft))} von {formatSeconds((session.minutes || 0) * 60)}.</p>}
        {!!Object.keys(byKap).length && (
          <div className="result-grid">
            {Object.entries(byKap).map(([kap, v]) => (
              <span key={kap}><b>{kap}</b>{v.ok}/{v.total}</span>
            ))}
          </div>
        )}
        {!!weak.length && (
          <div className="session-weak-list">
            <b>Schwache Karten</b>
            {weak.map((item) => (
              <span key={item.card_id}>
                VO{item.kap}: {item.card?.subname || item.card?.source || "Karte"} · {RATING_LABELS[item.rating]}
                {item.feedback_reason ? ` · ${reasonLabel(item.feedback_reason)}` : ""}
              </span>
            ))}
          </div>
        )}
        {!!tomorrow.length && (
          <div className="session-next-focus">
            <b>Morgen zuerst</b>
            <span>{tomorrow.map(([kap]) => kap).join(" · ")}</span>
          </div>
        )}
        <button className="primary" onClick={finish}>Zurueck</button>
      </section>
    );
  }

  if (!card) {
    return (
      <section className="done">
        <Check size={32} />
        <h2>Keine Karten faellig</h2>
        <p>Alles sauber. Du kannst spaeter wiederkommen oder im Dashboard ein einzelnes Kapitel starten.</p>
        <button className="primary" onClick={finish}>Zurueck</button>
      </section>
    );
  }

  return (
    <section className="study">
      <div className="study-top">
        <button onClick={finish}><ArrowLeft size={16} /> Zurueck</button>
        <div className="progress"><span style={{ width: `${progress}%` }} /></div>
        <span>{session.idx + 1}/{cards.length}</span>
        {isTimedExam && <span className={`study-timer ${secondsLeft <= 60 ? "urgent" : ""}`}>{formatSeconds(secondsLeft)}</span>}
        <button onClick={startEdit}><Edit3 size={16} /> Bearbeiten</button>
      </div>
      {editing ? (
        <article className="study-card study-edit-card">
          <div className="study-meta">
            <span className="deck-pill">VO{card.kap}</span>
            <span>{card.subname}</span>
            <span>Quelle: {card.source}</span>
          </div>
          <EditableCardPreview
            question={draft.q || ""}
            answer={draft.a || ""}
            onQuestion={(next) => setDraft({ ...draft, q: next })}
            onAnswer={(next) => setDraft({ ...draft, a: next })}
          />
          <label>Notiz
            <input value={draft.review_note || ""} onChange={(e) => setDraft({ ...draft, review_note: e.target.value })} />
          </label>
          <div className="button-row-inline">
            <button className="primary" disabled={savingEdit} onClick={() => saveEdit("active")}><Check size={16} /> Speichern</button>
            <button disabled={savingEdit} onClick={summarizeEdit}>Zusammenfassen</button>
            <button disabled={savingEdit} onClick={() => { setEditing(false); setEditMsg(""); }}><X size={16} /> Abbrechen</button>
            <button disabled={savingEdit} onClick={() => saveEdit("needs_review")}>Review markieren</button>
          </div>
          {editMsg && <div className="form-msg">{editMsg}</div>}
        </article>
      ) : (
      <article className="study-card">
        <div className="study-meta">
          <span className="deck-pill">VO{card.kap}</span>
          <span>{card.subname}</span>
          <span>Quelle: {card.source}</span>
          <span>faellig: {formatDate(card.due)}</span>
        </div>
        {editMsg && <div className="form-msg">{editMsg}</div>}
        <QuestionContent html={card.q} />
        <div className="card-report-strip">
          <span>Karte melden</span>
          {CARD_REPORT_REASONS.map(([key, label]) => (
            <button key={key} type="button" disabled={savingEdit} onClick={() => markForWorkshop(key)}>
              {label}
            </button>
          ))}
          {reportMsg && <em>{reportMsg}</em>}
        </div>
        {revealed ? (
          <>
            <AnswerContent html={card.a} />
            <div className="feedback-strip">
              <span>Nochmal-Grund</span>
              {REVIEW_REASONS.map(([key, label]) => (
                <button
                  key={key}
                  className={feedbackReason === key ? "active" : ""}
                  onClick={() => setFeedbackReason(feedbackReason === key ? "" : key)}
                  type="button"
                >
                  {label}
                </button>
              ))}
              <button type="button" disabled={savingEdit} onClick={() => markForWorkshop()}>
                In Werkstatt
              </button>
            </div>
            <div className="ratings">
              {[1, 2, 3, 4].map((r) => (
                <button key={r} className={`rating r${r}`} onClick={() => rate(r)}>
                  <b>{RATING_LABELS[r]}</b>
                  <span>{preview[r] || ""}</span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <button className="primary reveal" onClick={() => setRevealed(true)}>Antwort aufdecken</button>
        )}
      </article>
      )}
    </section>
  );
}

function Dashboard({ startSession, module }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api(`/api/dashboard?module=${encodeURIComponent(module)}`).then(setData).catch(() => {});
  }, [module]);
  if (!data) return <div className="loading">Dashboard laedt...</div>;
  const maxReviews = Math.max(1, ...data.timeline.map((d) => d.reviews || 0));
  return (
    <>
      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Dashboard</h2>
            <p>{data.forecast.summary}</p>
          </div>
          <div className="forecast-score compact"><b>{data.forecast.label}</b><span>{data.forecast.band}</span></div>
        </div>
        <div className="chart-grid">
          <div className="chart">
            <h3>Reviews</h3>
            <div className="spark-bars">
              {data.timeline.map((d) => (
                <span key={d.date} title={`${d.date}: ${d.reviews} Reviews`}>
                  <i style={{ height: `${Math.max(4, (d.reviews / maxReviews) * 100)}%` }} />
                </span>
              ))}
            </div>
          </div>
          <div className="chart">
            <h3>Kapitelabdeckung</h3>
            <div className="coverage-bars">
              {data.chapters.map((ch) => (
                <div key={ch.kap}>
                  <span>VO{ch.kap}</span>
                  <b><i style={{ width: `${ch.progress}%` }} /></b>
                  <em>{ch.progress}%</em>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="panel">
        <h2>Kapitel</h2>
        <div className="chapter-list">
          {data.chapters.map((ch) => (
            <button key={ch.kap} className="chapter-row" onClick={() => startSession("anki", ch.kap)}>
              <span>VO{ch.kap}</span>
              <b>{ch.name}</b>
              <em>{ch.seen}/{ch.total} gesehen</em>
              <i>{ch.due} faellig</i>
            </button>
          ))}
        </div>
      </section>

      <WeaknessHeatmap items={data.weaknesses || []} startSession={startSession} />
      <TagPanel tags={data.tags || []} />
    </>
  );
}

function ExamScorePanel({ prognosis }) {
  if (!prognosis) return null;
  return (
    <section className="panel exam-score-panel">
      <div>
        <h2>Pruefungs-Score-Prognose</h2>
        <p>{prognosis.next_step}</p>
      </div>
      <div className="forecast-score compact"><b>{prognosis.label}</b><span>gesamt</span></div>
      <div className="exam-blocks">
        {(prognosis.blocks || []).map((b) => (
          <div key={b.block}>
            <span>{b.block}</span>
            <b>{b.label}</b>
            <i><em style={{ width: `${b.score}%` }} /></i>
            <small>{b.detail}</small>
          </div>
        ))}
      </div>
    </section>
  );
}

function MasteryPanel({ mastery }) {
  const topics = mastery?.topics || [];
  if (!topics.length) return null;
  return (
    <section className="panel mastery-panel">
      <div className="section-head">
        <div>
          <h2>Themen-Mastery</h2>
          <p>Ampel je pruefungsnahem Thema, berechnet aus passenden Karten, Fehlern und Wiederholungen.</p>
        </div>
      </div>
      <div className="mastery-grid">
        {topics.map((topic) => (
          <article key={topic.topic} className={`mastery-card ${topic.status}`}>
            <div>
              <b>{topic.topic}</b>
              <span>{topic.score}%</span>
            </div>
            <p>{topic.detail}</p>
            <div className="mini-card-list">
              {(topic.cards || []).slice(0, 3).map((card) => (
                <span key={card.id}>VO{card.kap}: {card.title}</span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function FormulaChecklistPanel({ checklist, onStart }) {
  if (!checklist) return null;
  const groups = [
    ["draw", "Muss ich zeichnen koennen", checklist.draw || []],
    ["explain", "Muss ich erklaeren koennen", checklist.explain || []],
  ];
  return (
    <section className="panel formula-checklist">
      <div className="section-head">
        <div>
          <h2>Formel- und Reaktionschecklisten</h2>
          <p>Getrennt nach Zeichnen/Skizzieren und Erklaeren. Im Trainer kann Manuel seine Skizze fotografieren.</p>
        </div>
        <button onClick={onStart}>Skizzenmodus starten</button>
      </div>
      <div className="checklist-grid">
        {groups.map(([key, title, items]) => (
          <div key={key}>
            <h3>{title}</h3>
            {(items || []).slice(0, 10).map((item) => (
              <span key={item.id} className={item.score >= 70 ? "ok" : item.score >= 45 ? "mid" : "low"}>
                <b>VO{item.kap}</b>{item.title}<em>{item.score}%</em>
              </span>
            ))}
          </div>
        ))}
      </div>
    </section>
  );
}

function MediaTrainingPanel({ checklist, onFormula, onPhotos }) {
  const drawCount = checklist?.draw?.length || 0;
  const explainCount = checklist?.explain?.length || 0;
  return (
    <section className="panel media-training-panel">
      <div className="section-head">
        <div>
          <h2>Foto- und Formelmodus</h2>
          <p>Strukturen, Reaktionsgleichungen und Schemata aktiv zeichnen, fotografieren und als Karte speichern.</p>
        </div>
      </div>
      <div className="media-actions">
        <button className="primary" onClick={onFormula}>
          <b>{drawCount}</b>
          <span>Skizzen-/Formelmodus</span>
          <em>Zeichnen, fotografieren, selbst bewerten</em>
        </button>
        <button onClick={onPhotos}>
          <b>{explainCount}</b>
          <span>Foto-Queue</span>
          <em>Karten mit Fotoempfehlung gezielt abarbeiten</em>
        </button>
      </div>
    </section>
  );
}

function FinalPlanPanel({ plan }) {
  if (!plan) return null;
  return (
    <section className="panel final-plan">
      <div className="section-head">
        <div>
          <h2>7-Tage-Endspurtplan</h2>
          <p>{plan.rule}</p>
        </div>
        <span className="deck-pill">bis {plan.exam_date}</span>
      </div>
      <div className="final-days">
        {(plan.days || []).map((day) => (
          <article key={day.date}>
            <b>{day.date}</b>
            <h3>{day.title}</h3>
            <ul>{day.tasks.map((task) => <li key={task}>{task}</li>)}</ul>
            {!!day.focus?.length && <p>{day.focus.join(" - ")}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function toggleArrayValue(values = [], value) {
  return values.includes(value) ? values.filter((v) => v !== value) : [...values, value];
}

function ExamMetaControls({ confidence = "", onConfidence, errorTypes = [], onErrorTypes }) {
  return (
    <div className="exam-meta-controls">
      <div>
        <b>Confidence</b>
        <span>
          {CONFIDENCE_LEVELS.map(([key, label]) => (
            <button key={key} className={confidence === key ? "active" : ""} onClick={() => onConfidence(confidence === key ? "" : key)}>
              {label}
            </button>
          ))}
        </span>
      </div>
      <div>
        <b>Fehlerart</b>
        <span>
          {EXAM_ERROR_TYPES.map(([key, label]) => (
            <button key={key} className={errorTypes.includes(key) ? "active" : ""} onClick={() => onErrorTypes(toggleArrayValue(errorTypes, key))}>
              {label}
            </button>
          ))}
        </span>
      </div>
    </div>
  );
}

function AttemptHistoryPanel({ history }) {
  if (!history) return null;
  const attempts = history.attempts || [];
  const errors = history.errors || [];
  return (
    <section className="panel attempt-history">
      <div className="section-head">
        <div>
          <h2>Pruefungsdiagnostik</h2>
          <p>Verlauf, Fehlerarten und Confidence-Fallen aus den letzten offenen Pruefungen.</p>
        </div>
      </div>
      <div className="attempt-grid">
        <div>
          <h3>Versuchsverlauf</h3>
          <div className="attempt-list">
            {attempts.length ? attempts.slice(0, 6).map((a) => (
              <span key={a.id}>
                <b>{a.pct}%</b>
                <em>{formatDate(a.created_at)} - {a.title}</em>
              </span>
            )) : <p className="muted">Noch keine offene Pruefung gespeichert.</p>}
          </div>
        </div>
        <div>
          <h3>Haeufige Fehlerarten</h3>
          <div className="error-chip-list">
            {errors.length ? errors.map((e) => (
              <span key={e.key}><b>{e.count}</b>{e.label}</span>
            )) : <p className="muted">Fehlerarten erscheinen nach der ersten Auswertung.</p>}
          </div>
        </div>
        <div>
          <h3>Confidence-Fallen</h3>
          <div className="trap-list">
            {(history.confidence_traps || []).length ? history.confidence_traps.map((trap) => (
              <span key={`${trap.attempt_id}-${trap.title}`}>
                <b>{trap.score}%</b>{trap.title}
              </span>
            )) : <p className="muted">Noch keine sicheren Fehlgriffe erkannt.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function RepairQueuePanel({ history, onStart }) {
  const queue = history?.repair_queue || [];
  return (
    <section className="panel repair-queue">
      <div className="section-head">
        <div>
          <h2>Nachlern-Queue</h2>
          <p>Automatisch aus partial/miss, Confidence-Fallen und Fehlerarten erzeugt.</p>
        </div>
        <button className="primary" disabled={!queue.length} onClick={onStart}>Queue starten</button>
      </div>
      <div className="repair-list">
        {queue.length ? queue.slice(0, 8).map((card) => (
          <span key={card.id}>
            <b>VO{card.kap}</b>
            {card.repair?.reason || card.subname || card.id}
            <em>{(card.repair?.error_types || []).map((key) => EXAM_ERROR_TYPES.find(([k]) => k === key)?.[1] || key).join(", ") || "Pruefungsfehler"}</em>
          </span>
        )) : <p className="muted">Sobald eine Pruefung bewertet ist, liegt hier der Reparaturstapel.</p>}
      </div>
    </section>
  );
}

function WeeklyPlanPanel({ plan }) {
  if (!plan) return null;
  return (
    <section className="panel weekly-plan">
      <div className="section-head">
        <div>
          <h2>Wochenansicht bis 21.09.</h2>
          <p>{plan.rule}</p>
        </div>
        <span className="deck-pill">{plan.exam_date}</span>
      </div>
      <div className="week-grid">
        {(plan.weeks || []).map((week) => (
          <article key={week.start}>
            <b>{week.start} - {week.end}</b>
            <h3>{week.phase}</h3>
            <ul>{(week.tasks || []).map((task) => <li key={task}>{task}</li>)}</ul>
            {!!week.focus?.length && <p>{week.focus.join(" - ")}</p>}
          </article>
        ))}
      </div>
    </section>
  );
}

function scoreForQuestion(scores = {}, question) {
  const values = { full: 1, partial: .5, miss: 0 };
  return (question.subquestions || []).reduce((sum, sub) => sum + (values[scores[sub.id]] ?? 0) * (sub.points || 0), 0);
}

function OpenExamRunner({ exam, module, onClose }) {
  const [idx, setIdx] = useState(0);
  const [revealed, setRevealed] = useState({});
  const [answers, setAnswers] = useState({});
  const [scores, setScores] = useState({});
  const [checklist, setChecklist] = useState({});
  const [confidence, setConfidence] = useState({});
  const [errorTypes, setErrorTypes] = useState({});
  const [startedAt, setStartedAt] = useState(Date.now());
  const [secondsLeft, setSecondsLeft] = useState((exam.minutes || 0) * 60);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const question = exam.questions[idx];
  const earned = (exam.questions || []).reduce((sum, q) => sum + scoreForQuestion(scores[q.card_id] || {}, q), 0);

  useEffect(() => {
    setSecondsLeft((exam.minutes || 0) * 60);
    setAnswers({});
    setScores({});
    setChecklist({});
    setConfidence({});
    setErrorTypes({});
    setRevealed({});
    setResult(null);
    setSubmitting(false);
    setIdx(0);
    setStartedAt(Date.now());
  }, [exam.id]);

  useEffect(() => {
    if (result) return undefined;
    const timer = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [result]);

  useEffect(() => {
    if (result || submitting || secondsLeft > 0) return;
    finish();
  }, [secondsLeft, result, submitting]);

  function mark(subId, value) {
    setScores((old) => ({
      ...old,
      [question.card_id]: { ...(old[question.card_id] || {}), [subId]: value },
    }));
  }

  function toggleChecklist(key) {
    setChecklist((old) => {
      const current = old[question.card_id] || [];
      const next = current.includes(key) ? current.filter((item) => item !== key) : [...current, key];
      return { ...old, [question.card_id]: next };
    });
  }

  async function finish() {
    if (submitting) return;
    setSubmitting(true);
    const checklistLabel = (key) => EXAM_CHECKLIST.find(([item]) => item === key)?.[1] || key;
    const payload = {
      module,
      mode: exam.mode,
      exam_id: exam.id,
      duration_seconds: Math.round((Date.now() - startedAt) / 1000),
      results: (exam.questions || []).map((q) => ({
        card_id: q.card_id,
        sub_scores: (q.subquestions || []).map((sub) => (scores[q.card_id] || {})[sub.id] || "miss"),
        confidence: confidence[q.card_id] || "",
        error_types: errorTypes[q.card_id] || [],
        answer_note: [
          answers[q.card_id] || "",
          (checklist[q.card_id] || []).length ? `Checkliste: ${(checklist[q.card_id] || []).map(checklistLabel).join(", ")}` : "",
        ].filter(Boolean).join("\n\n"),
      })),
    };
    try {
      const res = await api("/api/exam/open/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setResult(res);
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <section className="done exam-result">
        <Check size={32} />
        <h2>Pruefung ausgewertet</h2>
        <p>{result.earned} von {result.total} Punkten, {result.pct}% geschaetzt.</p>
        <div className="result-grid">
          {(exam.questions || []).map((q) => (
            <span key={q.card_id}><b>Frage {q.idx}</b>{scoreForQuestion(scores[q.card_id] || {}, q).toFixed(1)}/4</span>
          ))}
        </div>
        <p className="muted">Versuch gespeichert: {result.attempt_id}. Schwache Fragen liegen jetzt in der Nachlern-Queue.</p>
        <button className="primary" onClick={onClose}>Zurueck</button>
      </section>
    );
  }

  if (!question) return null;
  const currentScores = scores[question.card_id] || {};
  const currentErrors = errorTypes[question.card_id] || [];
  const currentAnswer = answers[question.card_id] || "";
  const currentChecklist = checklist[question.card_id] || [];
  const currentComparison = answerComparison(currentAnswer, question);
  const isFormulaMode = exam.mode === "formula";
  const rubric = question.rubric?.length ? question.rubric : question.subquestions || [];
  const totalRubricPoints = rubric.reduce((sum, item) => sum + (item.points || 0), 0);
  return (
    <section className="open-exam">
      <div className="exam-toolbar">
        <button onClick={onClose}><ArrowLeft size={16} /> Zurueck</button>
        <div className="timer">{formatSeconds(secondsLeft)}</div>
        <div className="progress"><span style={{ width: `${pct(idx + 1, exam.questions.length || 1)}%` }} /></div>
        <b>{earned.toFixed(1)}/{exam.total_points}</b>
      </div>
      <div className="exam-nav">
        {(exam.questions || []).map((q, i) => (
          <button key={q.card_id} className={i === idx ? "active" : ""} onClick={() => setIdx(i)}>
            {q.idx}
          </button>
        ))}
      </div>
      <article className="panel open-question">
        <div className="study-meta">
          <span className="deck-pill">{question.block}</span>
          <span>VO{question.kap}</span>
          <span>{question.source}</span>
          <span>{question.points} Punkte</span>
          {question.sketch_required && <span>Skizze erforderlich</span>}
        </div>
        <h2 dangerouslySetInnerHTML={{ __html: question.question }} />
        <label className="exam-answer-editor">
          {isFormulaMode ? "Meine Skizze / Formel / Antwort" : "Meine Antwort"}
          <PhotoTextarea
            rows={8}
            value={currentAnswer}
            onValue={(next) => setAnswers((old) => ({ ...old, [question.card_id]: next }))}
            placeholder={isFormulaMode ? "Formel, Reaktionsgleichung oder kurze Erklaerung notieren. Foto/Skizze kann direkt eingefuegt werden." : "Antwort wie in der Pruefung formulieren, danach mit Geruest und Musterantwort vergleichen."}
          />
        </label>
        <FormulaToolbar value={currentAnswer} onValue={(next) => setAnswers((old) => ({ ...old, [question.card_id]: next }))} />
        <PhotoButton
          label={isFormulaMode ? "Skizze/Foto einfuegen" : "Foto zur Antwort"}
          onInsert={(html) => setAnswers((old) => ({ ...old, [question.card_id]: appendHtml(old[question.card_id] || "", html) }))}
        />
        {!!currentAnswer.trim() && (
          <div className="exam-answer-preview">
            <b>Meine Antwort gerendert</b>
            <div dangerouslySetInnerHTML={{ __html: currentAnswer }} />
          </div>
        )}
        {!!currentAnswer.trim() && !!currentComparison.terms.length && (
          <div className="answer-coverage">
            <div>
              <b>Mustervergleich</b>
              <span>{currentComparison.score}% Abdeckung · {currentComparison.hits.length}/{currentComparison.terms.length} Begriffe</span>
            </div>
            <div className="coverage-chip-row">
              {currentComparison.hits.slice(0, 10).map((term) => <span key={term} className="hit">{term}</span>)}
              {currentComparison.missing.slice(0, 10).map((term) => <span key={term} className="miss">{term}</span>)}
            </div>
          </div>
        )}
        <div className="point-schema">
          <div>
            <h3>Punkteschema</h3>
            <span>{totalRubricPoints.toFixed(1).replace(".0", "")} Punkte</span>
          </div>
          {(rubric || []).map((item) => (
            <article key={item.id || `${item.category}-${item.prompt}`}>
              <b>{item.category}</b>
              <p>{item.prompt}</p>
              <em>{item.points} P</em>
            </article>
          ))}
        </div>
        <div className="exam-checklist">
          <b>Mustervergleich</b>
          {EXAM_CHECKLIST.map(([key, label]) => (
            <button key={key} type="button" className={currentChecklist.includes(key) ? "active" : ""} onClick={() => toggleChecklist(key)}>
              {label}
            </button>
          ))}
        </div>
        <div className="subquestion-list">
          {(question.subquestions || []).map((sub) => (
            <div key={sub.id} className="subquestion">
              <p><b>{sub.category}</b>{sub.prompt}</p>
              <span>{sub.points} P</span>
              <div>
                {EXAM_EVALS.map(([key, label]) => (
                  <button key={key} className={currentScores[sub.id] === key ? "active" : ""} onClick={() => mark(sub.id, key)}>
                    {label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <ExamMetaControls
          confidence={confidence[question.card_id] || ""}
          onConfidence={(value) => setConfidence((old) => ({ ...old, [question.card_id]: value }))}
          errorTypes={currentErrors}
          onErrorTypes={(values) => setErrorTypes((old) => ({ ...old, [question.card_id]: values }))}
        />
        <div className="button-row-inline">
          <button onClick={() => setRevealed((old) => ({ ...old, [question.card_id]: !old[question.card_id] }))}>
            {revealed[question.card_id] ? "Loesung ausblenden" : "Geruest & Loesung zeigen"}
          </button>
          <button disabled={idx === 0} onClick={() => setIdx(idx - 1)}>Zurueck</button>
          <button disabled={idx + 1 >= exam.questions.length} onClick={() => setIdx(idx + 1)}>Weiter</button>
          <button className="primary" disabled={submitting} onClick={finish}>{submitting ? "Wertet aus..." : "Auswerten"}</button>
        </div>
        {revealed[question.card_id] && (
          <div className="exam-solution">
            <h3>Antwort-Geruest</h3>
            {!!currentAnswer.trim() && (
              <div className="answer-compare">
                <div>
                  <h3>Meine Antwort</h3>
                  <div dangerouslySetInnerHTML={{ __html: currentAnswer }} />
                </div>
                <div>
                  <h3>Musterantwort</h3>
                  <AnswerContent html={question.answer} />
                </div>
              </div>
            )}
            <div className="scaffold-list">
              {(question.scaffold || []).map((item) => <span key={item}>{item}</span>)}
            </div>
            {!currentAnswer.trim() && <AnswerContent html={question.answer} />}
          </div>
        )}
      </article>
    </section>
  );
}

function OralExamRunner({ exam, module, onClose }) {
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [scores, setScores] = useState({});
  const [promptDepth, setPromptDepth] = useState({});
  const [revealed, setRevealed] = useState({});
  const [confidence, setConfidence] = useState({});
  const [errorTypes, setErrorTypes] = useState({});
  const [startedAt, setStartedAt] = useState(Date.now());
  const [secondsLeft, setSecondsLeft] = useState((exam.minutes || 0) * 60);
  const [result, setResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const question = exam.questions[idx];
  const currentKey = question?.card_id || "";
  const prompts = question?.oral_prompts || [];
  const shownPrompts = prompts.slice(0, Math.max(1, promptDepth[currentKey] || 1));
  const currentAnswer = answers[currentKey] || "";
  const currentScores = scores[currentKey] || {};
  const currentErrors = errorTypes[currentKey] || [];
  const comparison = question ? answerComparison(currentAnswer, question) : { terms: [], hits: [], missing: [], score: 0 };
  const earned = (exam.questions || []).reduce((sum, q) => sum + scoreForQuestion(scores[q.card_id] || {}, q), 0);

  useEffect(() => {
    setAnswers({});
    setScores({});
    setPromptDepth({});
    setRevealed({});
    setConfidence({});
    setErrorTypes({});
    setResult(null);
    setSubmitting(false);
    setIdx(0);
    setSecondsLeft((exam.minutes || 0) * 60);
    setStartedAt(Date.now());
  }, [exam.id]);

  useEffect(() => {
    if (result) return undefined;
    const timer = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [result]);

  useEffect(() => {
    if (result || submitting || secondsLeft > 0) return;
    finish();
  }, [secondsLeft, result, submitting]);

  function mark(subId, value) {
    setScores((old) => ({
      ...old,
      [currentKey]: { ...(old[currentKey] || {}), [subId]: value },
    }));
  }

  function nextPrompt() {
    setPromptDepth((old) => ({
      ...old,
      [currentKey]: Math.min(prompts.length, Math.max(1, old[currentKey] || 1) + 1),
    }));
  }

  async function finish() {
    if (submitting) return;
    setSubmitting(true);
    const payload = {
      module,
      mode: "oral",
      exam_id: exam.id,
      duration_seconds: Math.round((Date.now() - startedAt) / 1000),
      results: (exam.questions || []).map((q) => ({
        card_id: q.card_id,
        sub_scores: (q.subquestions || []).map((sub) => (scores[q.card_id] || {})[sub.id] || "miss"),
        confidence: confidence[q.card_id] || "",
        error_types: errorTypes[q.card_id] || [],
        answer_note: [
          answers[q.card_id] || "",
          `Nachfragen: ${(q.oral_prompts || []).slice(0, Math.max(1, promptDepth[q.card_id] || 1)).map((p) => p.label).join(", ")}`,
        ].filter(Boolean).join("\n\n"),
      })),
    };
    try {
      const res = await api("/api/exam/open/submit", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setResult(res);
    } finally {
      setSubmitting(false);
    }
  }

  if (result) {
    return (
      <section className="done exam-result">
        <Check size={32} />
        <h2>Pruefermodus ausgewertet</h2>
        <p>{result.earned} von {result.total} Punkten, {result.pct}% geschaetzt.</p>
        <div className="result-grid">
          {(exam.questions || []).map((q) => (
            <span key={q.card_id}><b>Frage {q.idx}</b>{scoreForQuestion(scores[q.card_id] || {}, q).toFixed(1)}/4</span>
          ))}
        </div>
        <p className="muted">Versuch gespeichert: {result.attempt_id}. Schwache Themen sind in der Nachlern-Queue.</p>
        <button className="primary" onClick={onClose}>Zurueck</button>
      </section>
    );
  }

  if (!question) return null;
  return (
    <section className="oral-exam">
      <div className="exam-toolbar">
        <button onClick={onClose}><ArrowLeft size={16} /> Zurueck</button>
        <div className="timer">{formatSeconds(secondsLeft)}</div>
        <div className="progress"><span style={{ width: `${pct(idx + 1, exam.questions.length || 1)}%` }} /></div>
        <b>{earned.toFixed(1)}/{exam.total_points}</b>
      </div>
      <div className="exam-nav">
        {(exam.questions || []).map((q, i) => (
          <button key={q.card_id} className={i === idx ? "active" : ""} onClick={() => setIdx(i)}>
            {q.idx}
          </button>
        ))}
      </div>
      <article className="panel oral-card">
        <div className="study-meta">
          <span className="deck-pill">Pruefer</span>
          <span>VO{question.kap}</span>
          <span>{question.block}</span>
          <span>{question.source}</span>
        </div>
        <div className="oral-stage">
          <span>Muendliche Frage</span>
          <h2 dangerouslySetInnerHTML={{ __html: question.question }} />
          <div className="oral-prompts">
            {shownPrompts.map((prompt) => (
              <article key={prompt.id}>
                <b>{prompt.label}</b>
                <p>{prompt.prompt}</p>
                <em>{prompt.focus}</em>
              </article>
            ))}
          </div>
          <button type="button" disabled={shownPrompts.length >= prompts.length} onClick={nextPrompt}>
            Nachfrage stellen
          </button>
        </div>
        <label className="exam-answer-editor">
          Antwortnotiz
          <PhotoTextarea
            rows={7}
            value={currentAnswer}
            onValue={(next) => setAnswers((old) => ({ ...old, [currentKey]: next }))}
            placeholder="Frei erklaeren, dann Stichworte hier notieren. Nachfragen erst aufdecken, wenn die erste Antwort sitzt."
          />
        </label>
        <FormulaToolbar value={currentAnswer} onValue={(next) => setAnswers((old) => ({ ...old, [currentKey]: next }))} />
        <PhotoButton label="Skizze/Foto zur Antwort" onInsert={(html) => setAnswers((old) => ({ ...old, [currentKey]: appendHtml(old[currentKey] || "", html) }))} />
        {!!currentAnswer.trim() && !!comparison.terms.length && (
          <div className="answer-coverage oral-coverage">
            <div>
              <b>Antwortabdeckung</b>
              <span>{comparison.score}% · {comparison.hits.length}/{comparison.terms.length} Begriffe getroffen</span>
            </div>
            <div className="coverage-chip-row">
              {comparison.hits.slice(0, 8).map((term) => <span key={term} className="hit">{term}</span>)}
              {comparison.missing.slice(0, 8).map((term) => <span key={term} className="miss">{term}</span>)}
            </div>
          </div>
        )}
        <div className="oral-score-grid">
          {(question.subquestions || []).map((sub) => (
            <article key={sub.id}>
              <div>
                <b>{sub.category}</b>
                <p>{sub.prompt}</p>
              </div>
              <span>{sub.points} P</span>
              <em>
                {EXAM_EVALS.map(([key, label]) => (
                  <button key={key} className={currentScores[sub.id] === key ? "active" : ""} onClick={() => mark(sub.id, key)}>
                    {label}
                  </button>
                ))}
              </em>
            </article>
          ))}
        </div>
        <ExamMetaControls
          confidence={confidence[currentKey] || ""}
          onConfidence={(value) => setConfidence((old) => ({ ...old, [currentKey]: value }))}
          errorTypes={currentErrors}
          onErrorTypes={(values) => setErrorTypes((old) => ({ ...old, [currentKey]: values }))}
        />
        <div className="button-row-inline">
          <button onClick={() => setRevealed((old) => ({ ...old, [currentKey]: !old[currentKey] }))}>
            {revealed[currentKey] ? "Loesung ausblenden" : "Musterantwort zeigen"}
          </button>
          <button disabled={idx === 0} onClick={() => setIdx(idx - 1)}>Zurueck</button>
          <button disabled={idx + 1 >= exam.questions.length} onClick={() => setIdx(idx + 1)}>Weiter</button>
          <button className="primary" disabled={submitting} onClick={finish}>{submitting ? "Wertet aus..." : "Pruefermodus abschliessen"}</button>
        </div>
        {revealed[currentKey] && (
          <div className="exam-solution">
            <h3>Musterantwort und Geruest</h3>
            <div className="scaffold-list">
              {(question.scaffold || []).map((item) => <span key={item}>{item}</span>)}
            </div>
            <AnswerContent html={question.answer} />
          </div>
        )}
      </article>
    </section>
  );
}

function ArchiveCorrectionRunner({ exam, module, onClose }) {
  const [idx, setIdx] = useState(0);
  const [answers, setAnswers] = useState({});
  const [scores, setScores] = useState({});
  const [rubricScores, setRubricScores] = useState({});
  const [confidence, setConfidence] = useState({});
  const [errorTypes, setErrorTypes] = useState({});
  const [revealed, setRevealed] = useState({});
  const [startedAt, setStartedAt] = useState(Date.now());
  const [result, setResult] = useState(null);
  const questions = exam.questions || [];
  const question = questions[idx];
  const keyFor = (q, i) => `${i}:${q.topic}`;
  const currentKey = question ? keyFor(question, idx) : "";
  const done = Object.keys(scores).length;

  useEffect(() => {
    setIdx(0);
    setAnswers({});
    setScores({});
    setRubricScores({});
    setConfidence({});
    setErrorTypes({});
    setRevealed({});
    setResult(null);
    setStartedAt(Date.now());
  }, [exam.id]);

  function scoreFromRubric(items = {}, rubric = []) {
    const values = { full: 1, partial: .5, miss: 0 };
    const marked = rubric.map((r) => values[items[r.id]] ?? 0);
    if (!marked.length) return "";
    const ratio = marked.reduce((sum, n) => sum + n, 0) / marked.length;
    return ratio >= .85 ? "full" : ratio >= .35 ? "partial" : "miss";
  }

  function markRubric(rubricId, value) {
    const nextForQuestion = { ...(rubricScores[currentKey] || {}), [rubricId]: value };
    const derived = scoreFromRubric(nextForQuestion, question.rubric || []);
    setRubricScores((old) => ({ ...old, [currentKey]: nextForQuestion }));
    if (derived) setScores((old) => ({ ...old, [currentKey]: derived }));
  }

  async function finish() {
    const payload = {
      module,
      exam_id: exam.id,
      duration_seconds: Math.round((Date.now() - startedAt) / 1000),
      results: questions.map((q, i) => {
        const key = keyFor(q, i);
        const rubric = rubricScores[key] || {};
        return {
          topic: q.topic,
          score: scores[key] || "miss",
          card_ids: (q.matches || []).map((m) => m.id),
          note: answers[key] || "",
          confidence: confidence[key] || "",
          error_types: errorTypes[key] || [],
          rubric_scores: (q.rubric || []).map((r) => rubric[r.id] || "miss"),
        };
      }),
    };
    const res = await api("/api/exam/archive/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setResult(res);
  }

  if (result) {
    return (
      <section className="done exam-result">
        <Check size={32} />
        <h2>Archivbogen korrigiert</h2>
        <p>{result.earned} von {result.total} Punkten, {result.pct}% geschaetzt. {result.touched} Karten wurden ins Qualitaetssystem gespiegelt.</p>
        <p className="muted">Versuch gespeichert: {result.attempt_id}. Partial und Miss landen automatisch in der Nachlern-Queue.</p>
        <button className="primary" onClick={onClose}>Zurueck zum Pruefungsplatz</button>
      </section>
    );
  }

  if (!question) return null;
  const currentScore = scores[currentKey] || "";
  const currentRubric = rubricScores[currentKey] || {};
  const currentErrors = errorTypes[currentKey] || [];
  return (
    <section className="correction-runner">
      <div className="exam-toolbar">
        <button onClick={onClose}><ArrowLeft size={16} /> Zurueck</button>
        <div className="timer">{done}/{questions.length}</div>
        <div className="progress"><span style={{ width: `${pct(done, questions.length || 1)}%` }} /></div>
        <b>{exam.title}</b>
      </div>
      <div className="exam-nav">
        {questions.map((q, i) => (
          <button key={keyFor(q, i)} className={i === idx ? "active" : ""} onClick={() => setIdx(i)}>
            {i + 1}
          </button>
        ))}
      </div>
      <article className="panel archive-correction-card">
        <div className="study-meta">
          <span className="deck-pill">{exam.source}</span>
          <span>{question.points} Punkte</span>
        </div>
        <h2>{question.topic}</h2>
        <label>Freie Antwort / Stichworte
          <PhotoTextarea
            rows={7}
            value={answers[currentKey] || ""}
            onValue={(next) => setAnswers((old) => ({ ...old, [currentKey]: next }))}
            placeholder="Antwort wie in der Pruefung notieren, dann selbst nach Raster bewerten."
          />
        </label>
        <FormulaToolbar value={answers[currentKey] || ""} onValue={(next) => setAnswers((old) => ({ ...old, [currentKey]: next }))} />
        <div className="correction-score">
          {EXAM_EVALS.map(([key, label]) => (
            <button
              key={key}
              className={currentScore === key ? "active" : ""}
              onClick={() => setScores((old) => ({ ...old, [currentKey]: key }))}
            >
              {label}
            </button>
          ))}
        </div>
        <div className="rubric-checklist">
          {(question.rubric || []).map((item) => (
            <div key={item.id}>
              <p><b>{item.category}</b>{item.prompt}</p>
              <span>{item.points} P</span>
              <em>
                {EXAM_EVALS.map(([key, label]) => (
                  <button key={key} className={currentRubric[item.id] === key ? "active" : ""} onClick={() => markRubric(item.id, key)}>
                    {label}
                  </button>
                ))}
              </em>
            </div>
          ))}
        </div>
        <ExamMetaControls
          confidence={confidence[currentKey] || ""}
          onConfidence={(value) => setConfidence((old) => ({ ...old, [currentKey]: value }))}
          errorTypes={currentErrors}
          onErrorTypes={(values) => setErrorTypes((old) => ({ ...old, [currentKey]: values }))}
        />
        <div className="button-row-inline">
          <button onClick={() => setRevealed((old) => ({ ...old, [currentKey]: !old[currentKey] }))}>
            {revealed[currentKey] ? "Raster ausblenden" : "Bewertungsraster zeigen"}
          </button>
          <button disabled={idx === 0} onClick={() => setIdx(idx - 1)}>Zurueck</button>
          <button disabled={idx + 1 >= questions.length} onClick={() => setIdx(idx + 1)}>Weiter</button>
          <button className="primary" onClick={finish}>Archivbogen abschliessen</button>
        </div>
        {revealed[currentKey] && (
          <div className="correction-raster">
            <div>
              <h3>Erwartete Punkte</h3>
              <ul>{(question.rubric || []).map((r) => <li key={r.id}>{r.category}: {r.prompt} ({r.points} P)</li>)}</ul>
            </div>
            <div>
              <h3>Passende Karten</h3>
              <div className="match-strip">
                {(question.matches || []).map((m) => (
                  <span key={m.id}>VO{m.kap}: {m.title}</span>
                ))}
              </div>
            </div>
          </div>
        )}
      </article>
    </section>
  );
}

function ExamArchive({ archive, onStartCorrection }) {
  const exams = archive?.exams || [];
  const [selectedId, setSelectedId] = useState("");
  const selected = exams.find((e) => e.id === selectedId) || exams[0];
  useEffect(() => {
    if (!selectedId && exams[0]) setSelectedId(exams[0].id);
  }, [archive?.module, exams.length, selectedId]);
  if (!selected) return <p className="muted">Noch keine Archivansicht fuer dieses Modul.</p>;
  return (
    <section className="archive-layout">
      <div className="archive-list">
        {exams.map((exam) => (
          <button key={exam.id} className={selected.id === exam.id ? "active" : ""} onClick={() => setSelectedId(exam.id)}>
            <b>{exam.title}</b>
            <span>{exam.source}</span>
          </button>
        ))}
      </div>
      <div className="archive-paper">
        <div className="archive-paper-head">
          <h3>{selected.title}</h3>
          <button className="primary" onClick={() => onStartCorrection?.(selected)}>Korrektur starten</button>
        </div>
        {(selected.questions || []).map((q, i) => (
          <article key={`${selected.id}-${q.topic}`}>
            <div>
              <b>{i + 1}. {q.topic}</b>
              <span>{q.points} Punkte</span>
            </div>
            <ul>{(q.rubric || []).map((r) => <li key={r.id}>{r.category}: {r.prompt} ({r.points} P)</li>)}</ul>
            <div className="match-strip">
              {(q.matches || []).map((m) => (
                <span key={m.id}>VO{m.kap}: {m.title}</span>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ExamPage({ startExam, startSession, module }) {
  const [count, setCount] = useState(20);
  const [mode, setMode] = useState("mixed");
  const [exam, setExam] = useState(null);
  const [correction, setCorrection] = useState(null);
  const [prognosis, setPrognosis] = useState(null);
  const [archive, setArchive] = useState(null);
  const [mastery, setMastery] = useState(null);
  const [checklist, setChecklist] = useState(null);
  const [finalPlan, setFinalPlan] = useState(null);
  const [weeklyPlan, setWeeklyPlan] = useState(null);
  const [history, setHistory] = useState(null);

  async function loadExamMeta() {
    const base = `module=${encodeURIComponent(module)}`;
    const [nextPrognosis, nextArchive, nextMastery, nextChecklist, nextFinalPlan, nextWeeklyPlan, nextHistory] = await Promise.all([
      api(`/api/exam/prognosis?${base}`).catch(() => null),
      api(`/api/exam/archive?${base}`).catch(() => null),
      api(`/api/exam/mastery?${base}`).catch(() => null),
      api(`/api/exam/formula-checklist?${base}`).catch(() => null),
      api(`/api/exam/final-plan?${base}`).catch(() => null),
      api(`/api/exam/weekly-plan?${base}`).catch(() => null),
      api(`/api/exam/history?${base}`).catch(() => null),
    ]);
    setPrognosis(nextPrognosis);
    setArchive(nextArchive);
    setMastery(nextMastery);
    setChecklist(nextChecklist);
    setFinalPlan(nextFinalPlan);
    setWeeklyPlan(nextWeeklyPlan);
    setHistory(nextHistory);
  }

  useEffect(() => {
    loadExamMeta();
  }, [module]);

  async function startOpen(nextMode) {
    const res = await api(`/api/exam/open?module=${encodeURIComponent(module)}&mode=${encodeURIComponent(nextMode)}`);
    setCorrection(null);
    setExam(res);
  }

  async function startFormula() {
    const res = await api(`/api/exam/formulas?module=${encodeURIComponent(module)}&n=10`);
    setCorrection(null);
    setExam(res);
  }

  async function startOral() {
    const res = await api(`/api/exam/oral?module=${encodeURIComponent(module)}&n=5`);
    setCorrection(null);
    setExam(res);
  }

  async function closeRunner() {
    setExam(null);
    setCorrection(null);
    await loadExamMeta();
  }

  if (correction) return <ArchiveCorrectionRunner exam={correction} module={module} onClose={closeRunner} />;
  if (exam?.mode === "oral") return <OralExamRunner exam={exam} module={module} onClose={closeRunner} />;
  if (exam) return <OpenExamRunner exam={exam} module={module} onClose={closeRunner} />;

  return (
    <section className="exam-workbench">
      <div className="panel exam-hero-panel">
        <div className="section-head">
          <div>
            <h2>Pruefungsarbeitsplatz</h2>
            <p>Offene TU-Fragen, Antwortgerueste, Mini-Pruefungen und Formeltraining.</p>
          </div>
          <Target size={26} />
        </div>
        <div className="exam-actions-grid">
          <button className="primary" onClick={startOral}>V2 Pruefermodus</button>
          <button className="primary" onClick={() => startOpen("full")}>2h-Pruefung starten</button>
          <button onClick={() => startOpen("mini")}>Schwaechen-Mini-Pruefung</button>
          <button onClick={() => startOpen("explain")}>Kann ich erklaeren?</button>
          <button onClick={startFormula}>Skizzen-/Formelmodus</button>
        </div>
      </div>

      <ExamScorePanel prognosis={prognosis} />
      <AttemptHistoryPanel history={history} />
      <RepairQueuePanel history={history} onStart={() => startSession?.("repair")} />
      <MediaTrainingPanel checklist={checklist} onFormula={startFormula} onPhotos={() => startSession?.("photos")} />
      <MasteryPanel mastery={mastery} />
      <FormulaChecklistPanel checklist={checklist} onStart={startFormula} />
      <WeeklyPlanPanel plan={weeklyPlan} />
      <FinalPlanPanel plan={finalPlan} />

      <section className="panel exam-panel">
        <div className="section-head">
          <div>
            <h2>Karten-Drill</h2>
            <p>Schneller Recall-Modus als Warm-up vor der offenen Simulation.</p>
          </div>
        </div>
        <div className="form-grid">
          <label>Anzahl
            <select value={count} onChange={(e) => setCount(Number(e.target.value))}>
              {[10, 20, 30, 40, 60].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
          <label>Modus
            <select value={mode} onChange={(e) => setMode(e.target.value)}>
              <option value="mixed">Gemischt</option>
              <option value="weak">Schwachstellen</option>
            </select>
          </label>
          <button onClick={() => startExam(count, mode)}>Karten-Drill starten</button>
        </div>
      </section>

      <section className="panel">
        <div className="section-head">
          <div>
            <h2>Alte Pruefungen</h2>
            <p>Beispielboegen als Themenraster mit passenden Lernkarten daneben.</p>
          </div>
        </div>
        <ExamArchive archive={archive} onStartCorrection={setCorrection} />
      </section>
    </section>
  );
}

function ManualCardPage({ onDone, module }) {
  const [form, setForm] = useState({ kap: 1, q: "", a: "", source: "Manuell" });
  const [msg, setMsg] = useState("");
  async function submit(e) {
    e.preventDefault();
    setMsg("");
    try {
      await api("/api/cards/manual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, module, kap: Number(form.kap) }),
      });
      setForm({ kap: form.kap, q: "", a: "", source: "Manuell" });
      setMsg("Karte gespeichert.");
      onDone?.();
    } catch (err) {
      setMsg(err.message);
    }
  }
  return (
    <section className="panel">
      <h2>Eigene Karte hinzufuegen</h2>
      <form className="card-form" onSubmit={submit}>
        <label>VO
          <select value={form.kap} onChange={(e) => setForm({ ...form, kap: Number(e.target.value) })}>
            {Array.from({ length: 11 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>VO{n}</option>)}
          </select>
        </label>
        <label>Quelle
          <input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} />
        </label>
        <EditableCardPreview
          question={form.q}
          answer={form.a}
          onQuestion={(next) => setForm({ ...form, q: next })}
          onAnswer={(next) => setForm({ ...form, a: next })}
        />
        <button className="primary"><Plus size={16} /> Speichern</button>
      </form>
      {msg && <div className="form-msg">{msg}</div>}
    </section>
  );
}

const IMPORT_SAMPLE = `Frage,Antwort,VO,Quelle
"Erlaeutern Sie das Kontaktverfahren.","SO2 wird katalytisch zu SO3 oxidiert; daraus entsteht H2SO4.",1,"Eigene Notizen"
"Was ist der Zweck der Chloralkali-Elektrolyse?","Herstellung von Chlor, Natronlauge und Wasserstoff aus NaCl-Loesung.",2,"Eigene Notizen"`;

function CardImportPage({ onDone, module }) {
  const [format, setFormat] = useState("csv");
  const [source, setSource] = useState("Import");
  const [defaultKap, setDefaultKap] = useState(1);
  const [dedupe, setDedupe] = useState(true);
  const [text, setText] = useState(IMPORT_SAMPLE);
  const [preview, setPreview] = useState(null);
  const [selectedIdx, setSelectedIdx] = useState(0);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  const payload = {
    module,
    format,
    source,
    default_kap: Number(defaultKap),
    text,
    dedupe,
  };

  async function readFile(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    const lower = file.name.toLowerCase();
    if (lower.endsWith(".json")) setFormat("json");
    else if (lower.endsWith(".tsv")) setFormat("tsv");
    else setFormat("csv");
    setSource(file.name.replace(/\.[^.]+$/, "") || "Import");
    setText(await file.text());
    setPreview(null);
    setMsg(`${file.name} geladen.`);
    e.target.value = "";
  }

  async function previewImport(e) {
    e?.preventDefault?.();
    setBusy("preview");
    setMsg("");
    try {
      const res = await api("/api/cards/import/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setPreview(res);
      setSelectedIdx(0);
      setMsg(`${res.valid || 0} neue Karte(n) erkannt${res.skipped_duplicates ? `, ${res.skipped_duplicates} Duplikat(e) uebersprungen` : ""}.`);
    } catch (err) {
      setMsg(err.message || "Vorschau fehlgeschlagen");
    } finally {
      setBusy("");
    }
  }

  async function importCards() {
    setBusy("import");
    setMsg("");
    try {
      const res = await api("/api/cards/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      setMsg(`${res.imported || 0} Karte(n) importiert${res.skipped_duplicates ? `, ${res.skipped_duplicates} Duplikat(e) uebersprungen` : ""}.`);
      setPreview(null);
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Import fehlgeschlagen");
    } finally {
      setBusy("");
    }
  }

  const cards = preview?.cards || [];
  const selected = cards[Math.min(selectedIdx, Math.max(cards.length - 1, 0))];
  return (
    <section className="import-layout">
      <div className="panel import-panel">
        <div className="section-head">
          <div>
            <h2>Karten importieren</h2>
            <p>CSV, TSV oder JSON in Anki-Style: Frage, Antwort, optional VO und Quelle.</p>
          </div>
          <ClipboardList size={22} />
        </div>
        <form className="card-form" onSubmit={previewImport}>
          <label>Format
            <select value={format} onChange={(e) => setFormat(e.target.value)}>
              <option value="csv">CSV</option>
              <option value="tsv">TSV</option>
              <option value="json">JSON</option>
            </select>
          </label>
          <label>Standard-VO
            <select value={defaultKap} onChange={(e) => setDefaultKap(Number(e.target.value))}>
              {Array.from({ length: 11 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>VO{n}</option>)}
            </select>
          </label>
          <label>Quelle
            <input value={source} onChange={(e) => setSource(e.target.value)} />
          </label>
          <label className="checkbox-label">
            <input type="checkbox" checked={dedupe} onChange={(e) => setDedupe(e.target.checked)} />
            Duplikate ueberspringen
          </label>
          <label className="file-input-label">Datei
            <input type="file" accept=".csv,.tsv,.json,.txt,text/csv,application/json" onChange={readFile} />
          </label>
          <label className="import-textarea">Importdaten
            <textarea value={text} onChange={(e) => { setText(e.target.value); setPreview(null); }} rows={14} />
          </label>
          <div className="button-row-inline">
            <button className="primary" disabled={!!busy || !text.trim()}><Search size={16} /> Vorschau</button>
            <button type="button" disabled={busy === "import" || !(preview?.valid)} onClick={importCards}>
              <Plus size={16} /> Importieren
            </button>
          </div>
        </form>
        {msg && <div className="form-msg">{msg}</div>}
      </div>

      <div className="panel import-preview-panel">
        <div className="section-head">
          <div>
            <h2>Import-Vorschau</h2>
            <p>{preview ? `${preview.valid || 0} gueltig · ${(preview.errors || []).length} Hinweis(e)` : "Noch keine Vorschau berechnet."}</p>
          </div>
        </div>
        {!!(preview?.errors || []).length && (
          <div className="import-errors">
            {(preview.errors || []).slice(0, 8).map((err) => <span key={err}>{err}</span>)}
          </div>
        )}
        <div className="import-preview-grid">
          <div className="import-card-list">
            {cards.length ? cards.map((card, idx) => (
              <button key={`${card.kap}-${idx}-${card.q}`} className={idx === selectedIdx ? "active" : ""} onClick={() => setSelectedIdx(idx)}>
                <b>VO{card.kap} · {card.source}</b>
                <span>{stripHtmlText(card.q).slice(0, 110)}</span>
              </button>
            )) : <p className="muted">Nach der Vorschau erscheinen hier die erkannten Karten.</p>}
          </div>
          <div>
            {selected ? <CardRenderPreview question={selected.q || ""} answer={selected.a || ""} /> : <p className="muted">Keine Karte ausgewaehlt.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function CardReviewPage({ onDone, module }) {
  const [status, setStatus] = useState("needs_review");
  const [kap, setKap] = useState("");
  const [tag, setTag] = useState("");
  const [media, setMedia] = useState("all");
  const [query, setQuery] = useState("");
  const [data, setData] = useState({ cards: [], summary: {} });
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    const qs = new URLSearchParams({ status, limit: "80", module });
    if (kap) qs.set("kap", kap);
    if (tag) qs.set("tag", tag);
    if (media !== "all") qs.set("media", media);
    if (query) qs.set("q", query);
    const res = await api(`/api/cards?${qs}`);
    setData(res);
    setSelected(res.cards?.[0] || null);
  }
  useEffect(() => { load().catch(() => {}); }, [status, kap, tag, media, module]);

  function select(card) {
    setSelected({ ...card });
    setMsg("");
  }
  async function save(nextStatus = selected?.status || "active") {
    if (!selected) return;
    const res = await api(`/api/cards/${encodeURIComponent(selected.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        q: selected.q,
        a: selected.a,
        status: nextStatus,
        review_note: selected.review_note || "",
      }),
    });
    setSelected(res.card);
    setMsg("Gespeichert.");
    await load();
    onDone?.();
  }
  return (
    <section className="quality-layout">
      <div className="panel quality-list">
        <div className="section-head">
          <div>
            <h2>Kartenqualitaet</h2>
            <p>Holprige Karten bearbeiten, deaktivieren oder freigeben.</p>
          </div>
          <Search size={22} />
        </div>
        <div className="filters">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="needs_review">Review empfohlen</option>
            <option value="active">Aktiv</option>
            <option value="suspended">Deaktiviert</option>
            <option value="all">Alle</option>
          </select>
          <select value={kap} onChange={(e) => setKap(e.target.value)}>
            <option value="">Alle VO</option>
            {Array.from({ length: 11 }, (_, i) => i + 1).map((n) => <option key={n} value={n}>VO{n}</option>)}
          </select>
          <select value={media} onChange={(e) => setMedia(e.target.value)}>
            <option value="all">Alle Medien</option>
            <option value="with_photo">Mit Foto</option>
            <option value="without_photo">Ohne Foto</option>
            <option value="photo_recommended">Foto empfohlen</option>
          </select>
          <input placeholder="Tag" value={tag} onChange={(e) => setTag(e.target.value)} />
          <input placeholder="Suchen" value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load()} />
          <button onClick={load}>Filtern</button>
        </div>
        <div className="quality-summary">
          <span>aktiv {data.summary?.active || 0}</span>
          <span>Review {data.summary?.needs_review || 0}</span>
          <span>aus {data.summary?.suspended || 0}</span>
        </div>
        <div className="quality-items">
          {(data.cards || []).map((card) => (
            <button key={card.id} className={selected?.id === card.id ? "active" : ""} onClick={() => select(card)}>
              <b>VO{card.kap} · {card.status}</b>
              <em>{[(card.tags || []).join(" · "), card.has_photo ? "Foto" : "", card.photo_recommended ? "Foto empfohlen" : "", card.sketch_required ? "Skizze" : ""].filter(Boolean).join(" · ")}</em>
              <span dangerouslySetInnerHTML={{ __html: card.q }} />
            </button>
          ))}
        </div>
      </div>
      <div className="panel quality-editor">
        {selected ? (
          <>
            <EditableCardPreview
              question={selected.q || ""}
              answer={selected.a || ""}
              onQuestion={(next) => setSelected({ ...selected, q: next })}
              onAnswer={(next) => setSelected({ ...selected, a: next })}
            />
            <label>Notiz
              <input value={selected.review_note || ""} onChange={(e) => setSelected({ ...selected, review_note: e.target.value })} />
            </label>
            <div className="button-row-inline">
              <button className="primary" onClick={() => save("active")}><Edit3 size={16} /> Aktiv speichern</button>
              <button onClick={() => save("needs_review")}>Review markieren</button>
              <button onClick={() => save("suspended")}>Deaktivieren</button>
            </div>
            {msg && <div className="form-msg">{msg}</div>}
          </>
        ) : <p className="muted">Keine Karte ausgewaehlt.</p>}
      </div>
    </section>
  );
}

function WorkshopPage({ module, onDone }) {
  const [data, setData] = useState({ categories: [], queue: [], duplicates: [] });
  const [category, setCategory] = useState("queue");
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function selectSummary(card) {
    if (!card?.id) return;
    const res = await api(`/api/cards/${encodeURIComponent(card.id)}`);
    setSelected(res.card);
    setMsg("");
  }

  async function load(forcePick = false) {
    const res = await api(`/api/workshop?module=${encodeURIComponent(module)}&limit=10`);
    setData(res);
    if ((forcePick || !selected) && res.queue?.[0]) await selectSummary(res.queue[0]);
  }

  useEffect(() => {
    setSelected(null);
    setCategory("queue");
    load(true).catch(() => {});
  }, [module]);

  const activeCards = category === "queue"
    ? data.queue || []
    : (data.categories || []).find((item) => item.key === category)?.cards || [];
  const activeCategory = (data.categories || []).find((item) => item.key === category);
  const selectedSummary = [
    ...(data.queue || []),
    ...(data.categories || []).flatMap((item) => item.cards || []),
  ].find((card) => card.id === selected?.id);

  async function save(nextStatus = selected?.status || "active") {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await api(`/api/cards/${encodeURIComponent(selected.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          q: selected.q,
          a: selected.a,
          status: nextStatus,
          review_note: selected.review_note || "",
        }),
      });
      setSelected(res.card);
      setMsg(nextStatus === "suspended" ? "Deaktiviert." : "Gespeichert.");
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function improve() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await api(`/api/cards/${encodeURIComponent(selected.id)}/improve`, { method: "POST" });
      setSelected(res.card);
      setMsg("Pruefungsnah geglaettet und aktiviert.");
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Verbessern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function summarize() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await api(`/api/cards/${encodeURIComponent(selected.id)}/summarize`, { method: "POST" });
      setSelected(res.card);
      setMsg("Karte gekuerzt. Bitte kurz gegenpruefen.");
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Kuerzen fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function repairFormulas() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await api(`/api/cards/${encodeURIComponent(selected.id)}/repair-formulas`, { method: "POST" });
      setSelected(res.card);
      setMsg("Formeln repariert.");
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Formel-Reparatur fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function repairAllFormulas() {
    setBusy(true);
    try {
      const res = await api(`/api/workshop/repair-formulas?module=${encodeURIComponent(module)}&limit=200`, { method: "POST" });
      setMsg(`${res.fixed || 0} Karten mit Formel-Fix gespeichert.`);
      await load(true);
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Batch-Reparatur fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="workshop-layout">
      <div className="panel workshop-side">
        <div className="section-head">
          <div>
            <h2>Karten-Werkstatt</h2>
            <p>Review-Queue, Duplikate, Nonsense und Karten mit Skizzen- oder Foto-Bedarf.</p>
          </div>
          <Edit3 size={22} />
        </div>
        <div className="workshop-categories">
          <button className={category === "queue" ? "active" : ""} onClick={() => setCategory("queue")}>
            <b>{data.queue?.length || 0}</b>
            <span>Review-Queue</span>
          </button>
          {(data.categories || []).map((item) => (
            <button key={item.key} className={category === item.key ? "active" : ""} onClick={() => setCategory(item.key)}>
              <b>{item.count || 0}</b>
              <span>{item.label}</span>
            </button>
          ))}
        </div>
        {activeCategory?.description && <p className="muted workshop-hint">{activeCategory.description}</p>}
        {category === "formula" && (
          <button className="primary" disabled={busy} onClick={repairAllFormulas}>
            Alle Formel-Fixes speichern
          </button>
        )}
        <div className="workshop-list">
          {activeCards.length ? activeCards.map((card) => (
            <button key={`${category}-${card.id}`} className={selected?.id === card.id ? "active" : ""} onClick={() => selectSummary(card)}>
              <b>VO{card.kap} · {card.status}</b>
              <span>{card.title}</span>
              <em>{(card.issues || []).map(issueLabel).join(" · ") || "Hinweis"}</em>
            </button>
          )) : <p className="muted">In dieser Kategorie ist gerade nichts offen.</p>}
        </div>
        {!!(data.duplicates || []).length && (
          <div className="duplicate-groups">
            <h3>Duplikat-Finder</h3>
            {data.duplicates.slice(0, 4).map((group) => (
              <article key={group.signature}>
                <b>{group.cards?.length || 0} aehnliche Karten</b>
                <div>
                  {(group.cards || []).map((card) => (
                    <button key={card.id} onClick={() => selectSummary(card)}>VO{card.kap}: {card.title}</button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        )}
      </div>

      <div className="panel workshop-editor">
        {selected ? (
          <>
            <div className="study-meta">
              <span className="deck-pill">VO{selected.kap}</span>
              <span>{selected.source}</span>
              <span>{selected.status}</span>
              {selected.photo_recommended && <span>Foto empfohlen</span>}
              {selected.sketch_required && <span>Skizze erforderlich</span>}
            </div>
            <div className="issue-pills">
              {(selectedSummary?.issues || []).map((issue) => (
                <span key={issue}>{issueLabel(issue)}</span>
              ))}
            </div>
            <EditableCardPreview
              question={selected.q || ""}
              answer={selected.a || ""}
              onQuestion={(next) => setSelected({ ...selected, q: next })}
              onAnswer={(next) => setSelected({ ...selected, a: next })}
            />
            <label>Notiz
              <input value={selected.review_note || ""} onChange={(e) => setSelected({ ...selected, review_note: e.target.value })} />
            </label>
            <div className="button-row-inline">
              <button className="primary" disabled={busy} onClick={improve}><Edit3 size={16} /> Auto verbessern</button>
              <button disabled={busy} onClick={summarize}>Zusammenfassen</button>
              <button disabled={busy} onClick={repairFormulas}>Formeln reparieren</button>
              <button disabled={busy} onClick={() => save("active")}>Aktiv speichern</button>
              <button disabled={busy} onClick={() => save("needs_review")}>Review</button>
              <button disabled={busy} onClick={() => save("suspended")}>Deaktivieren</button>
            </div>
            {msg && <div className="form-msg">{msg}</div>}
          </>
        ) : (
          <div className="done">
            <Check size={30} />
            <h2>Werkstatt leer</h2>
            <p>Gerade ist keine Karte ausgewaehlt.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function TriagePage({ module, onDone }) {
  const [data, setData] = useState({ cards: [], tags: [], remaining: 0 });
  const [idx, setIdx] = useState(0);
  const [tag, setTag] = useState("");
  const [draft, setDraft] = useState(null);
  const [reason, setReason] = useState("");
  const [msg, setMsg] = useState("");

  async function load(nextTag = tag) {
    const qs = new URLSearchParams({ module, limit: "10" });
    if (nextTag) qs.set("tag", nextTag);
    const res = await api(`/api/triage?${qs}`);
    setData(res);
    setIdx(0);
    setDraft(res.cards?.[0] ? { ...res.cards[0] } : null);
  }
  useEffect(() => { load().catch(() => {}); }, [module]);
  useEffect(() => {
    setDraft(data.cards?.[idx] ? { ...data.cards[idx] } : null);
    setReason("");
    setMsg("");
  }, [idx, data.cards]);

  async function act(action) {
    if (!draft) return;
    await api(`/api/cards/${encodeURIComponent(draft.id)}/triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        action,
        q: draft.q,
        a: draft.a,
        reason,
        review_note: action === "needs_review" || action === "suspend"
          ? [reason ? reasonLabel(reason) : "", draft.review_note || "Bitte spaeter ueberarbeiten"].filter(Boolean).join(": ")
          : "",
      }),
    });
    setMsg("Gespeichert.");
    if (idx + 1 < data.cards.length) setIdx(idx + 1);
    else await load();
    onDone?.();
  }

  function pickTag(nextTag) {
    setTag(nextTag);
    load(nextTag).catch(() => {});
  }

  return (
    <section className="triage-layout">
      <div className="panel triage-side">
        <div className="section-head">
          <div>
            <h2>Karten-Triage</h2>
            <p>{data.remaining || 0} ungepruefte Karten in diesem Modul.</p>
          </div>
          <ClipboardList size={22} />
        </div>
        <div className="tag-cloud compact">
          <button className={!tag ? "active" : ""} onClick={() => pickTag("")}>Alle</button>
          {(data.tags || []).slice(0, 12).map((t) => (
            <button key={t.tag} className={tag === t.tag ? "active" : ""} onClick={() => pickTag(t.tag)}>
              <b>{t.tag}</b><span>{t.total}</span>
            </button>
          ))}
        </div>
      </div>
      <div className="panel triage-card">
        {draft ? (
          <>
            <div className="study-meta">
              <span className="deck-pill">VO{draft.kap}</span>
              <span>{draft.source}</span>
              <span>Score {draft.quality_score || 0}</span>
              {(draft.tags || []).map((t) => <span key={t}>{t}</span>)}
            </div>
            <EditableCardPreview
              question={draft.q || ""}
              answer={draft.a || ""}
              onQuestion={(next) => setDraft({ ...draft, q: next })}
              onAnswer={(next) => setDraft({ ...draft, a: next })}
            />
            <div className="reason-options">
              {TRIAGE_REASONS.map(([key, label]) => (
                <button
                  key={key}
                  className={reason === key ? "active" : ""}
                  onClick={() => setReason(reason === key ? "" : key)}
                  type="button"
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="button-row-inline">
              <button className="primary" onClick={() => act("approve")}><Check size={16} /> Gut</button>
              <button onClick={() => act("approve")}><Edit3 size={16} /> Bearbeiten speichern</button>
              <button onClick={() => act("needs_review")}>Review</button>
              <button onClick={() => act("suspend")}>Aus</button>
            </div>
            {msg && <div className="form-msg">{msg}</div>}
          </>
        ) : (
          <div className="done">
            <Check size={30} />
            <h2>Triage leer</h2>
            <p>Fuer diesen Filter gibt es gerade keine Karten.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function PerformancePanel() {
  const [perf, setPerf] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    setMsg("");
    try {
      setPerf(await api("/api/performance"));
    } catch (err) {
      setMsg(err.message || "Performance-Daten nicht verfuegbar");
    }
  }

  useEffect(() => { load().catch(() => {}); }, []);
  const endpoints = perf?.endpoints || [];
  const assets = perf?.assets || [];
  return (
    <div className="panel performance-panel">
      <div className="section-head">
        <div>
          <h3>Performance-Monitor</h3>
          <p>{perf ? `${perf.window} API-Samples · Assets ${formatBytes(perf.asset_bytes || 0)} · DB ${formatBytes(perf.db?.bytes || 0)}` : "Ladezeiten und Bundle-Groessen messen."}</p>
        </div>
        <button onClick={load}><RefreshCw size={16} /> Aktualisieren</button>
      </div>
      <div className="perf-grid">
        <div>
          <b>Langsame Endpunkte</b>
          {endpoints.length ? endpoints.slice(0, 6).map((item) => (
            <span key={item.path}>
              <em>{item.path}</em>
              <strong>{item.p95_ms} ms</strong>
              <small>{item.count}x · avg {item.avg_ms} ms</small>
            </span>
          )) : <p className="muted">Noch keine API-Samples in diesem Prozess.</p>}
        </div>
        <div>
          <b>Bundle</b>
          {assets.length ? assets.slice(0, 6).map((asset) => (
            <span key={asset.name}>
              <em>{asset.name}</em>
              <strong>{formatBytes(asset.bytes)}</strong>
            </span>
          )) : <p className="muted">Assets erscheinen nach dem Production-Build.</p>}
        </div>
      </div>
      {msg && <div className="form-msg">{msg}</div>}
    </div>
  );
}

function QualityAuditPanel({ module, setRoute }) {
  const [audit, setAudit] = useState(null);
  const [selected, setSelected] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  async function load() {
    setBusy(true);
    setMsg("");
    try {
      const res = await api(`/api/quality/audit?module=${encodeURIComponent(module)}&limit=12`);
      setAudit(res);
      setSelected(res.items?.[0] || null);
    } catch (err) {
      setMsg(err.message || "Audit fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function applyPreview(item = selected) {
    if (!item?.card?.id || !item.preview) return;
    setBusy(true);
    setMsg("");
    try {
      await api(`/api/cards/${encodeURIComponent(item.card.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          q: item.preview.q,
          a: item.preview.a,
          status: item.preview.status || "active",
          review_note: item.preview.review_note || "",
        }),
      });
      setMsg("Vorschlag gespeichert.");
      await load();
    } catch (err) {
      setMsg(err.message || "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="panel audit-panel">
      <div className="section-head">
        <div>
          <h3>Automatischer Karten-Audit</h3>
          <p>Findet Englisch, Nonsense, fehlenden Kontext, zu lange Antworten und Formelprobleme mit Speichervorschau.</p>
        </div>
        <button className="primary" disabled={busy} onClick={load}>Audit pruefen</button>
      </div>
      {audit && (
        <>
          <div className="issue-pills">
            {(audit.issue_counts || []).slice(0, 8).map((item) => (
              <span key={item.issue}>{item.label}: {item.count}</span>
            ))}
          </div>
          <div className="audit-grid">
            <div className="audit-list">
              {(audit.items || []).map((item) => (
                <button key={item.card.id} className={selected?.card?.id === item.card.id ? "active" : ""} onClick={() => setSelected(item)}>
                  <b>VO{item.card.kap} · {(item.issues || []).map(issueLabel).join(", ")}</b>
                  <span>{item.card.title}</span>
                </button>
              ))}
            </div>
            <div className="audit-preview">
              {selected ? (
                <>
                  <CardRenderPreview question={selected.preview?.q || ""} answer={selected.preview?.a || ""} />
                  <div className="button-row-inline">
                    <button className="primary" disabled={busy} onClick={() => applyPreview(selected)}>Vorschlag speichern</button>
                    <button onClick={() => setRoute("workshop")}>In Werkstatt oeffnen</button>
                  </div>
                </>
              ) : <p className="muted">Keine Auditkarte ausgewaehlt.</p>}
            </div>
          </div>
        </>
      )}
      {msg && <div className="form-msg">{msg}</div>}
    </div>
  );
}

function QualityCenter({ data, setRoute, module, startSession }) {
  const quality = data.quality || {};
  const autoQuality = data.auto_quality || {};
  const reasons = quality.reasons || [];
  const recent = quality.recent || [];
  const max = Math.max(1, ...reasons.map((r) => r.count || 0));

  return (
    <section className="quality-center">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2>Qualitaetszentrum</h2>
            <p>Kartenfehler sammeln, schlechte Extraktionen finden und die Lernkarten gezielt glaetten.</p>
          </div>
          <ClipboardList size={22} />
        </div>
        <div className="quality-metrics">
          <span><b>{quality.unchecked || 0}</b> ungeprueft</span>
          <span><b>{quality.needs_review || 0}</b> im Review</span>
          <span><b>{quality.suspended || 0}</b> deaktiviert</span>
          <span><b>{quality.with_photo || 0}</b> mit Foto</span>
          <span><b>{quality.photo_recommended || 0}</b> Foto empfohlen</span>
          <span><b>{autoQuality.moved || 0}</b> auto markiert</span>
        </div>
        <div className="button-row-inline">
          <button className="primary" onClick={() => setRoute("triage")}><ClipboardList size={16} /> Triage starten</button>
          <button onClick={() => setRoute("workshop")}><Edit3 size={16} /> Werkstatt</button>
          <button onClick={() => setRoute("quality")}><Search size={16} /> Karten bearbeiten</button>
          <button onClick={() => setRoute("photos")}><ImagePlus size={16} /> Fotopool</button>
          <button onClick={() => startSession?.("photos")}><ImagePlus size={16} /> Foto-Queue</button>
        </div>
      </div>

      <div className="quality-center-grid">
        <PerformancePanel />
        <QualityAuditPanel module={module} setRoute={setRoute} />
        <div className="panel">
          <h3>Haeufige Gruende</h3>
          <div className="reason-bars">
            {reasons.length ? reasons.map((r) => (
              <div className="reason-row" key={`${r.event_type}-${r.reason}`}>
                <b>{reasonLabel(r.reason)}</b>
                <span><i style={{ width: `${Math.max(7, pct(r.count, max))}%` }} /></span>
                <em>{r.count}</em>
              </div>
            )) : <p className="muted">Noch keine Qualitaetsgruende erfasst.</p>}
          </div>
        </div>

        <div className="panel">
          <h3>Letzte Meldungen</h3>
          <div className="quality-feed">
            {recent.length ? recent.map((item) => (
              <article key={item.id || `${item.card_id}-${item.created_at}`}>
                <div>
                  <b>{reasonLabel(item.reason)}</b>
                  <span>VO{item.kap || "?"} - {item.status || "aktiv"} - {formatDate(item.created_at)}</span>
                </div>
                <p>{item.note || item.question || item.card_id}</p>
              </article>
            )) : <p className="muted">Sobald Karten markiert werden, erscheint hier der Verlauf.</p>}
          </div>
        </div>
      </div>
    </section>
  );
}

function PhotoPoolPage({ onDone, startSession }) {
  const [pool, setPool] = useState({ photos: [], total: 0, used: 0, unused: 0, bytes: 0, skipped: 0 });
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState("");

  async function load() {
    const res = await api("/api/uploads/photos");
    setPool(res);
  }

  useEffect(() => {
    load().catch((err) => setMsg(err.message));
  }, []);

  async function deletePhoto(filename) {
    if (!window.confirm(`${filename} loeschen?`)) return;
    setBusy(filename);
    setMsg("");
    try {
      await api(`/api/uploads/photos/${encodeURIComponent(filename)}`, { method: "DELETE" });
      setMsg("Foto geloescht.");
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Loeschen fehlgeschlagen");
    } finally {
      setBusy("");
    }
  }

  async function cleanup() {
    setBusy("cleanup");
    setMsg("");
    try {
      const res = await api("/api/uploads/photos/cleanup", { method: "POST" });
      setMsg(`${res.count || 0} ungenutzte Fotos geloescht.`);
      await load();
      onDone?.();
    } catch (err) {
      setMsg(err.message || "Aufraeumen fehlgeschlagen");
    } finally {
      setBusy("");
    }
  }

  return (
    <section className="photo-pool-page">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2>Fotopool</h2>
            <p>Hochgeladene Kartenbilder, Nutzung und ungenutzte Dateien.</p>
          </div>
          <ImagePlus size={22} />
        </div>
        <div className="quality-metrics photo-metrics">
          <span><b>{pool.total || 0}</b> Fotos</span>
          <span><b>{pool.used || 0}</b> verwendet</span>
          <span><b>{pool.unused || 0}</b> ungenutzt</span>
          <span><b>{formatBytes(pool.bytes || 0)}</b> Speicher</span>
        </div>
        <div className="button-row-inline">
          <button className="primary" onClick={load}><RefreshCw size={16} /> Aktualisieren</button>
          <button onClick={() => startSession?.("photos")}><ImagePlus size={16} /> Foto-Queue starten</button>
          <button onClick={cleanup} disabled={busy === "cleanup" || !(pool.unused || 0)}>
            Ungenutzte loeschen
          </button>
        </div>
        {msg && <div className="form-msg">{msg}</div>}
        {!!pool.skipped && <div className="form-msg">{pool.skipped} Datei(en) konnten nicht gelesen werden.</div>}
      </div>

      <div className="photo-pool-grid">
        {(pool.photos || []).map((photo) => (
          <article className="photo-pool-item" key={photo.filename}>
            <button className="photo-thumb" type="button">
              <img src={photo.url} alt={photo.filename} />
            </button>
            <div className="photo-pool-meta">
              <b>{photo.filename}</b>
              <span>{formatBytes(photo.size)} · {formatDate(photo.modified_at)}</span>
              <em>{photo.used_count ? `${photo.used_count}x verwendet` : "ungenutzt"}</em>
            </div>
            {!!photo.used_count && (
              <div className="photo-usage-list">
                {(photo.used_by || []).map((item) => (
                  <span key={`${photo.filename}-${item.card_id}`}>
                    VO{item.kap || "?"} · {item.subname || item.source || item.card_id}
                  </span>
                ))}
              </div>
            )}
            <button
              onClick={() => deletePhoto(photo.filename)}
              disabled={!photo.unused || busy === photo.filename}
            >
              {busy === photo.filename ? "Loescht..." : "Loeschen"}
            </button>
          </article>
        ))}
      </div>
      {!(pool.photos || []).length && <div className="panel muted">Noch keine Fotos hochgeladen.</div>}
    </section>
  );
}

function App() {
  const isLogin = window.location.pathname === "/login";
  const [route, setRoute] = useState("home");
  const [module, setModule] = useState("organic");
  const [data, setData] = useState(null);
  const [session, setSession] = useState(null);
  const [lightbox, setLightbox] = useState(null);

  async function load() {
    setData(await api(`/api/stats?module=${encodeURIComponent(module)}`));
  }
  useEffect(() => {
    if (!isLogin) load().catch(() => {});
  }, [isLogin, module]);

  async function startSession(deck = "anki", kap = null) {
    const qs = new URLSearchParams({ limit: "30" });
    if (kap) qs.set("kap", String(kap));
    qs.set("module", module);
    const res = await api(`/api/study/${deck}?${qs}`);
    setSession({ deck, module, cards: res.cards || [], idx: 0, kap });
  }

  async function startExam(count = 20, mode = "mixed") {
    const qs = new URLSearchParams({ n: String(count), mode, module });
    const res = await api(`/api/exam/recall?${qs}`);
    setSession({
      deck: "exam",
      module,
      title: res.title || "Pruefungs-Karten-Drill",
      minutes: res.minutes || Math.max(5, Math.round((res.cards || []).length * .85)),
      cards: res.cards || [],
      idx: 0,
      mode,
      results: [],
      startedAt: Date.now(),
    });
  }

  async function finishSession() {
    setSession(null);
    await load();
  }

  const content = useMemo(() => {
    if (!data) return <div className="loading">Laedt...</div>;
    if (session) return <Study session={session} setSession={setSession} finish={finishSession} />;
    if (route === "dashboard") return <Dashboard startSession={startSession} module={module} />;
    if (route === "exam") return <ExamPage startExam={startExam} startSession={startSession} module={module} />;
    if (route === "quality-center") return <QualityCenter data={data} setRoute={setRoute} module={module} startSession={startSession} />;
    if (route === "workshop") return <WorkshopPage module={module} onDone={load} />;
    if (route === "triage") return <TriagePage module={module} onDone={load} />;
    if (route === "quality") return <CardReviewPage onDone={load} module={module} />;
    if (route === "photos") return <PhotoPoolPage onDone={load} startSession={startSession} />;
    if (route === "add") return <ManualCardPage onDone={load} module={module} />;
    if (route === "import") return <CardImportPage onDone={load} module={module} />;
    return <Home data={data} startSession={startSession} setRoute={setRoute} refresh={load} module={module} setModule={setModule} />;
  }, [data, session, route, module]);

  if (isLogin) return <Login />;
  return (
    <main
      className="wrap"
      onClick={(e) => {
        const img = e.target.closest?.("img.card-photo");
        if (!img) return;
        setLightbox({ src: img.getAttribute("src"), alt: img.getAttribute("alt") || "Foto" });
      }}
    >
      <AuthBar />
      <nav className="tabs">
        <button className={route === "home" ? "active" : ""} onClick={() => setRoute("home")}><BookOpenCheck size={16} /> Trainer</button>
        <button className={route === "dashboard" ? "active" : ""} onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
        <button className={route === "exam" ? "active" : ""} onClick={() => setRoute("exam")}><Target size={16} /> Pruefung</button>
        <button className={route === "quality-center" ? "active" : ""} onClick={() => setRoute("quality-center")}><ClipboardList size={16} /> Qualitaet</button>
        <button className={route === "workshop" ? "active" : ""} onClick={() => setRoute("workshop")}><Edit3 size={16} /> Werkstatt</button>
        <button className={route === "triage" ? "active" : ""} onClick={() => setRoute("triage")}><ClipboardList size={16} /> Triage</button>
        <button className={route === "quality" ? "active" : ""} onClick={() => setRoute("quality")}><ClipboardList size={16} /> Kartenqualitaet</button>
        <button className={route === "photos" ? "active" : ""} onClick={() => setRoute("photos")}><ImagePlus size={16} /> Fotopool</button>
        <button className={route === "add" ? "active" : ""} onClick={() => setRoute("add")}><Plus size={16} /> Eigene Karte</button>
        <button className={route === "import" ? "active" : ""} onClick={() => setRoute("import")}><ClipboardList size={16} /> Import</button>
      </nav>
      {content}
      <PhotoLightbox photo={lightbox} onClose={() => setLightbox(null)} />
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);

if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
