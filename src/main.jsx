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
  KeyRound,
  Mic,
  MicOff,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Target,
  Trophy,
  Volume2,
  VolumeX,
  X,
  AlertTriangle,
  Gauge,
  Sparkles,
  ListChecks,
  Award,
  Brain,
  CalendarClock,
  CalendarDays,
  ChevronDown,
  FlaskConical,
  ListOrdered,
  Split,
  Sun,
  Moon,
  FileText,
  Timer,
} from "lucide-react";
import "./styles.css";

const RATING_LABELS = { 1: "Nochmal", 2: "Schwer", 3: "Gut", 4: "Leicht" };
// Vaia-Prinzip: eine mit "Nochmal" bewertete Karte kommt so viele Karten spaeter wieder.
const REQUEUE_AHEAD = 3;
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
  source: "Quelle schwach",
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

function formatExamDate(s) {
  if (!s) return "Pruefung";
  return new Date(`${s}T12:00:00`).toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit", year: "numeric" });
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

function VoiceExamControls({ readText = "", value = "", onValue }) {
  const recognitionRef = useRef(null);
  const latestValueRef = useRef(value || "");
  const [listening, setListening] = useState(false);
  const [liveText, setLiveText] = useState("");
  const [msg, setMsg] = useState("");
  const SpeechRecognition = typeof window !== "undefined" ? (window.SpeechRecognition || window.webkitSpeechRecognition) : null;
  const canListen = Boolean(SpeechRecognition);
  const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    latestValueRef.current = value || "";
  }, [value]);

  useEffect(() => () => {
    recognitionRef.current?.abort?.();
    if (canSpeak) window.speechSynthesis.cancel();
  }, [canSpeak]);

  function speak() {
    if (!canSpeak) {
      setMsg("Vorlesen wird von diesem Browser nicht unterstuetzt.");
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(stripHtmlText(readText));
    utterance.lang = "de-AT";
    utterance.rate = .94;
    utterance.pitch = 1;
    const voice = window.speechSynthesis.getVoices().find((item) => /^de[-_]/i.test(item.lang));
    if (voice) utterance.voice = voice;
    utterance.onend = () => setMsg("");
    utterance.onerror = () => setMsg("Vorlesen fehlgeschlagen.");
    setMsg("Pruefer liest vor...");
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    if (!canSpeak) return;
    window.speechSynthesis.cancel();
    setMsg("Vorlesen gestoppt.");
  }

  function startListening() {
    if (!canListen) {
      setMsg("Mikro-Diktat wird von diesem Browser nicht unterstuetzt.");
      return;
    }
    recognitionRef.current?.abort?.();
    const recognition = new SpeechRecognition();
    recognition.lang = "de-AT";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.onstart = () => {
      setListening(true);
      setLiveText("");
      setMsg("Mikro hoert zu...");
    };
    recognition.onerror = (event) => {
      setMsg(event.error === "not-allowed" ? "Mikrofonzugriff blockiert." : "Diktat abgebrochen.");
      setListening(false);
    };
    recognition.onend = () => {
      setListening(false);
      setLiveText("");
      setMsg((old) => old === "Mikro hoert zu..." ? "Diktat beendet." : old);
    };
    recognition.onresult = (event) => {
      let finalText = "";
      let interimText = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const transcript = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += transcript;
        else interimText += transcript;
      }
      if (finalText.trim()) {
        const next = appendInline(latestValueRef.current, finalText.trim());
        latestValueRef.current = next;
        onValue?.(next);
      }
      setLiveText(interimText.trim());
    };
    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      setMsg("Mikro konnte nicht gestartet werden.");
      setListening(false);
    }
  }

  function stopListening() {
    recognitionRef.current?.stop?.();
    setListening(false);
  }

  return (
    <div className="voice-exam-controls">
      <div>
        <b>Voice-Pruefung</b>
        <span>{canListen || canSpeak ? "Vorlesen lassen und Antwort diktieren." : "Dieser Browser bietet keine Web-Speech-Funktionen."}</span>
      </div>
      <div className="voice-actions">
        <button type="button" onClick={speak} disabled={!readText.trim()}><Volume2 size={16} /> Vorlesen</button>
        <button type="button" onClick={stopSpeaking}><VolumeX size={16} /> Stop</button>
        {listening ? (
          <button type="button" className="active" onClick={stopListening}><MicOff size={16} /> Mikro stoppen</button>
        ) : (
          <button type="button" onClick={startListening}><Mic size={16} /> Mikro starten</button>
        )}
      </div>
      {(liveText || msg) && (
        <p>
          {liveText ? <strong>{liveText}</strong> : null}
          {msg ? <span>{msg}</span> : null}
        </p>
      )}
    </div>
  );
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

function currentTheme() {
  const t = (typeof document !== "undefined" && document.documentElement.getAttribute("data-theme")) || "light";
  return t === "dark" ? "dark" : "light";
}

function ThemeToggle() {
  const [theme, setTheme] = useState(currentTheme);
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("sr_theme", next); } catch (e) {}
    setTheme(next);
  };
  const dark = theme === "dark";
  return (
    <button
      className="theme-toggle"
      title={dark ? "Zu hellem Design wechseln" : "Zu dunklem Design wechseln"}
      aria-label={dark ? "Helles Design" : "Dunkles Design"}
      onClick={toggle}
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

function AuthBar() {
  const [user, setUser] = useState("");
  const [pwOpen, setPwOpen] = useState(false);
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
      <ThemeToggle />
      <button title="Passwort ändern" onClick={() => setPwOpen((v) => !v)}><KeyRound size={15} /></button>
      <button title="Abmelden" onClick={logout}><LogOut size={15} /></button>
      {pwOpen && <PasswordChange onClose={() => setPwOpen(false)} />}
    </div>
  );
}

function PasswordChange({ onClose }) {
  const [cur, setCur] = useState("");
  const [next, setNext] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault();
    if (next.length < 8) { setMsg("Neues Passwort: mindestens 8 Zeichen."); return; }
    setBusy(true); setMsg("");
    try {
      await api("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password: cur, new_password: next }),
      });
      setMsg("Passwort geändert. Andere Geräte wurden abgemeldet.");
      setCur(""); setNext("");
    } catch (err) {
      setMsg(err.message || "Änderung fehlgeschlagen.");
    } finally { setBusy(false); }
  }
  return (
    <form className="pw-change" onSubmit={submit}>
      <b>Passwort ändern</b>
      <input type="password" autoComplete="current-password" placeholder="Aktuelles Passwort"
        value={cur} onChange={(e) => setCur(e.target.value)} />
      <input type="password" autoComplete="new-password" placeholder="Neues Passwort (min. 8)"
        value={next} onChange={(e) => setNext(e.target.value)} />
      <div className="pw-change-row">
        <button className="primary" type="submit" disabled={busy || !cur || !next}>{busy ? "…" : "Speichern"}</button>
        <button type="button" onClick={onClose}>Schließen</button>
      </div>
      {msg && <span className="muted" style={{ fontSize: 12 }}>{msg}</span>}
    </form>
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
        <p>Chemische Technologien organischer und anorganischer Stoffe, fokussiert auf Manuels Pruefungen.</p>
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

function ReadinessCoach({ score, setRoute, startExam, startSession }) {
  if (!score) return null;
  const components = score.components || [];
  const blockers = score.blockers || [];
  return (
    <section className={`panel readiness-panel ${score.band || ""}`}>
      <div className="section-head">
        <div>
          <h2>Pruefungsreife</h2>
          <p>{score.next_step}</p>
        </div>
        <div className="readiness-score">
          <b>{score.overall || 0}%</b>
          <span>{score.band_label || score.status || "Status"}</span>
        </div>
      </div>
      <div className="readiness-main">
        <div className="readiness-components">
          {components.map((item) => (
            <div key={item.label}>
              <span>{item.label}</span>
              <b>{item.score}%</b>
              <i><em style={{ width: `${item.score}%` }} /></i>
              <small>{item.detail}</small>
            </div>
          ))}
        </div>
        <div className="readiness-blockers">
          <b>Blocker bis 80%</b>
          {blockers.slice(0, 5).map((item) => (
            <button key={item.key} onClick={() => item.kap ? startSession?.("anki", item.kap) : setRoute?.(item.route || "dashboard")}>
              <span>{item.label}</span>
              <em>{item.detail}</em>
            </button>
          ))}
          {!blockers.length && <p>Keine harte Luecke sichtbar. Jetzt mit einer Simulation absichern.</p>}
          <div className="button-row-inline">
            <button className="primary" onClick={() => startExam?.(12, "weak")}>Mini-Pruefung</button>
            <button onClick={() => setRoute?.("knowledge")}>Landkarte</button>
          </div>
        </div>
      </div>
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

function SourceAnchorPanel({ anchor, compact = false }) {
  if (!anchor) return null;
  return (
    <div className={`source-anchor-panel ${anchor.status || ""} ${compact ? "compact" : ""}`}>
      <div className="source-anchor-head">
        <div>
          <b>{anchor.anchor || "Quelle"}</b>
          <span>{anchor.source || "nicht gesetzt"}</span>
        </div>
        <em>{anchor.score ?? 0}% · {anchor.label || "Quelle"}</em>
      </div>
      {!compact && (
        <>
          <div className="source-anchor-tags">
            {(anchor.tags || []).slice(0, 6).map((tag) => <span key={tag}>{tag}</span>)}
            {(anchor.issues || []).slice(0, 4).map((issue) => <span key={issue} className="issue">{issue}</span>)}
          </div>
          {!!(anchor.derivation || []).length && (
            <div className="source-anchor-why">
              <b>Warum diese Antwort?</b>
              {(anchor.derivation || []).slice(0, 4).map((item) => <span key={item}>{item}</span>)}
            </div>
          )}
        </>
      )}
    </div>
  );
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

function HomePlanCard({ plan: d, startSession, startExam, setRoute }) {
  // Plan kommt direkt aus /api/stats (data.plan) - kein zweiter Roundtrip/Waterfall.
  if (!d) return null;

  const runTask = (t) => {
    if (t.kind === "review") startSession?.("anki");
    else if (t.kind === "new") startSession?.("anki", t.kap || null);
    else if (t.kind === "exam") startExam?.(t.count || 10, "weak");
    else if (t.kind === "mock") startExam?.(t.count || 20, "mixed");
    else if (t.kind === "fehlerbuch") setRoute?.("fehlerbuch");
  };
  const phaseColor = { aufbau: "#2980b9", festigen: "var(--warn-strong)", pruefung: "var(--bad)" }[d.phase?.key] || "var(--muted)";

  return (
    <section className="panel home-plan">
      <div className="section-head">
        <div>
          <h2>Dein Plan heute</h2>
          <p>
            <span className="plan-phase" style={{ background: phaseColor }}>{d.phase?.label}</span>
            {" "}· {d.days_left} Tage bis zur Prüfung · {d.capacity?.new_per_day} neu / {d.capacity?.reviews_per_day} Wdh pro Tag
          </p>
        </div>
        <button onClick={() => setRoute?.("studyplan")}><CalendarDays size={16} /> Ganzer Plan</button>
      </div>
      <div className="plan-today">
        {(d.today || []).slice(0, 3).map((t) => (
          <button key={t.key} className="plan-task" onClick={() => runTask(t)}>
            <div>
              <b>{t.title}</b>
              {t.detail && <span className="muted">{t.detail}</span>}
            </div>
            <span className="plan-task-go">Start →</span>
          </button>
        ))}
        {(d.today || []).length === 0 && (
          <p className="muted">Heute nichts Dringendes – halte deine Wiederholungen am Laufen.</p>
        )}
      </div>
    </section>
  );
}

function ExamReadinessStrip({ data, startSession, setRoute }) {
  // pass_prediction kommt direkt aus /api/stats (data.pass_prediction) - kein zweiter
  // Roundtrip auf /api/readiness-plan mehr, der Deck-/Kapitel-/Qualitaets-/Prognosedaten
  // nur neu berechnen wuerde (kein Waterfall vor dem Readiness-Bereich).
  const pp = data?.pass_prediction;
  const parts = pp?.parts || [];
  if (!pp || !parts.length) return null;
  const color = (s) => (s < 50 ? "var(--bad)" : s < 65 ? "var(--warn-strong)" : "var(--ok)");
  const weakest = pp.weakest_part;
  const pass = pp.would_pass;
  return (
    <section className="panel exam-strip">
      <div className="exam-strip-head">
        <div>
          <b className={`exam-verdict ${pass ? "ok" : "risk"}`}>{pass ? "✓ Auf Bestehenskurs" : "✗ Noch nicht bestehenssicher"}</b>
          <span className="muted"> · Regel: {pp.rule}</span>
        </div>
        <div className="exam-countdown"><b>{data.days_until_exam}</b> Tage bis zur Prüfung</div>
      </div>
      <div className="exam-teile">
        {parts.map((p) => (
          <button key={p.name} className={`exam-teil ${weakest && p.name === weakest.name ? "weakest" : ""}`}
            onClick={() => startSession("anki", null, p.name)} title={`${p.name} gezielt üben`}>
            <span className="exam-teil-top">
              <span className="exam-teil-dot" style={{ background: color(p.score) }} />
              <span className="exam-teil-name">{p.name}</span>
              <span className="exam-teil-score" style={{ color: color(p.score) }}>{p.score}%</span>
            </span>
            <i className="exam-teil-bar"><span style={{ width: `${Math.min(100, p.score)}%`, background: color(p.score) }} /><em /></i>
            {p.accuracy_blocks && <small className="exam-teil-warn">nur {p.accuracy}% richtig</small>}
          </button>
        ))}
      </div>
      <div className="exam-strip-foot">
        {weakest && (
          <button className="primary" onClick={() => startSession("anki", null, weakest.name)}>
            <Target size={15} /> Schwächsten Teil üben: {weakest.name}
          </button>
        )}
        <button onClick={() => setRoute("readiness")}><CalendarClock size={15} /> Ganzer Reifeplan</button>
      </div>
    </section>
  );
}

function Home({ data, startSession, startExam, setRoute, refresh, module, setModule, sessionSize, setSessionSize }) {
  const st = data.anki || {};
  const goal = data.daily_goal || {};
  const forecast = data.forecast || {};
  const examDate = formatExamDate(data.exam_date);
  return (
    <>
      <ModuleSwitch modules={data.modules || {}} active={module} onChange={setModule} />
      <section className="hero">
        <div className="days">{data.days_until_exam}</div>
        <div>
          <span className="hero-kicker">Technische Universität · Prüfungsvorbereitung</span>
          <h1>{data.title}</h1>
          <p>Manuels Anki-Style Trainer bis zur Pruefung am {examDate}.</p>
          <div className="hero-actions">
            <button className="primary" onClick={() => startSession("anki")}>Session starten</button>
            <label className="session-size" title="Karten pro Session">
              <select value={sessionSize} onChange={(e) => setSessionSize?.(Number(e.target.value))}>
                {[10, 15, 20, 25, 30, 40, 50].map((n) => <option key={n} value={n}>{n} Karten</option>)}
              </select>
            </label>
            <button onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
            <button onClick={() => setRoute("knowledge")}><Tag size={16} /> Landkarte</button>
            <button onClick={() => setRoute("workshop")}><Edit3 size={16} /> Werkstatt</button>
          </div>
        </div>
      </section>

      <ExamReadinessStrip data={data} startSession={startSession} setRoute={setRoute} />
      <XpCard xp={data.xp} streak={data.streak} />
      <HomePlanCard plan={data.plan} startSession={startSession} startExam={startExam} setRoute={setRoute} />
      <ReadinessCoach score={data.exam_score} setRoute={setRoute} startExam={startExam} startSession={startSession} />

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
  const [submitting, setSubmitting] = useState(false);
  const submittingRef = useRef(false);
  // Idempotenz-ID bleibt ueber Retries erhalten: geht nach erfolgreichem Commit nur die
  // HTTP-Antwort verloren, verwendet der naechste Klick DIESELBE ID -> der Server dedupt.
  const pendingReqId = useRef(null);
  const [secondsLeft, setSecondsLeft] = useState((session.minutes || 0) * 60);
  const isExam = session.deck === "exam";
  const isTimedExam = isExam && Number(session.minutes || 0) > 0;
  // Fortschritt an "gemeisterten" (mit Gut/Leicht beantworteten) EINZIGARTIGEN Karten messen -
  // sonst wuerde der Balken durch die Requeues (gleiche Karte mehrfach in der Queue) springen.
  const totalUnique = isExam ? cards.length : new Set(cards.map((c) => c.id)).size;
  const masteredUnique = isExam
    ? (session.results || []).length
    : new Set((session.results || []).filter((r) => r.rating >= 3).map((r) => r.card_id)).size;
  const remaining = Math.max(cards.length - session.idx, 0);
  const progress = isExam
    ? pct(session.idx, Math.max(cards.length, 1))
    : pct(masteredUnique, Math.max(totalUnique, 1));

  // Segmentierte Fortschrittsleiste im Wiederhol-Modus (StudySmarter-Stil):
  // ein Segment je EINZIGARTIGER Karte, gefaerbt nach der zuletzt gegebenen Bewertung.
  // Reihenfolge = erste Vorkommnisse in cards (Requeues fuegen nur bereits vorhandene
  // Karten wieder ein, nie neue -> stabile Ausgangsreihenfolge).
  let segments = null;
  if (!isExam) {
    const seen = new Set();
    const order = [];
    for (const c of cards) { if (!seen.has(c.id)) { seen.add(c.id); order.push(c.id); } }
    const latest = {};
    for (const r of (session.results || [])) latest[r.card_id] = r.rating;
    const curId = card?.id;
    const stateFor = (id) => {
      if (id === curId) return "current";
      const rt = latest[id];
      if (rt === undefined) return "unseen";
      return { 1: "again", 2: "ok", 3: "good", 4: "perfect" }[rt] || "good";
    };
    segments = order.map((id) => stateFor(id));
  }

  useEffect(() => {
    setRevealed(false);
    setPreview({});
    setFeedbackReason("");
    setEditing(false);
    setEditMsg("");
    setReportMsg("");
    setSavingEdit(false);
    submittingRef.current = false;
    setSubmitting(false);
    setDraft({ q: card?.q || "", a: card?.a || "", review_note: card?.review_note || "" });
    // An session.idx UND card.id koppeln: bei "Nochmal"/"Schwer" auf der letzten Karte
    // wird dieselbe Karte direkt wieder eingereiht - dann bleibt card.id gleich, aber
    // idx aendert sich. Ohne idx im Dep-Array liefe der Reset nicht und submittingRef
    // bliebe true -> die Session waere blockiert.
  }, [session.idx, card?.id]);

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

  // Mock-Exam: bei Abschluss serverseitig nach der echten Bestehensregel auswerten.
  // mockError ist terminal (kein automatischer Retry -> keine Endlosschleife); ein
  // expliziter Retry-Button setzt ihn zurueck.
  useEffect(() => {
    if (!session.done || !session.mock || session.mockReport || session.mockGrading || session.mockError) return;
    const examId = session.exam_id;
    // Verspaetete Antwort nur uebernehmen, wenn es noch dieselbe Mock-Session ist.
    const belongs = (old) => old && old.mock && old.done && old.exam_id === examId;
    setSession((old) => belongs(old) ? { ...old, mockGrading: true } : old);
    api("/api/mock-exam/grade", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        module: session.module,
        exam_id: examId,
        duration_seconds: session.elapsedSeconds ?? 0,
        results: (session.results || []).map((r) => ({ card_id: r.card_id, kap: r.kap, rating: r.rating })),
      }),
    })
      .then((rep) => setSession((old) => belongs(old) ? { ...old, mockReport: rep, mockGrading: false } : old))
      .catch(() => setSession((old) => belongs(old) ? { ...old, mockGrading: false, mockError: true } : old));
  }, [session.done, session.mock, session.mockReport, session.mockGrading, session.mockError, session.exam_id, session.module, session.results, session.elapsedSeconds, setSession]);

  async function rate(rating) {
    // Synchroner Guard: zwei schnelle Klicks passieren sonst beide den State-Check,
    // bevor React neu rendert - das verbuchte Review/XP doppelt und uebersprang eine Karte.
    if (submittingRef.current) return;
    submittingRef.current = true;
    setSubmitting(true);
    const reviewReason = rating === 1 ? (feedbackReason || "begriff_nicht_gewusst") : "";
    // Idempotenz-Schluessel pro Bewertung. Bereits vergebene ID (aus einem vorherigen,
    // evtl. schon committeten Versuch) WIEDERVERWENDEN - sonst wuerde ein Retry mit neuer
    // ID einen bereits verbuchten Review doppelt zaehlen, wenn nur die Antwort verloren ging.
    if (!pendingReqId.current) {
      pendingReqId.current = ((crypto.randomUUID && crypto.randomUUID()) ||
        (String(Date.now()) + "-" + Math.random().toString(36).slice(2))).slice(0, 64);
    }
    const requestId = pendingReqId.current;
    try {
      await api("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          card_id: card.id,
          rating,
          source: isExam ? "exam" : "review",
          feedback_reason: reviewReason,
          request_id: requestId,
        }),
      });
    } catch (err) {
      // ID NICHT zuruecksetzen -> der naechste Klick nutzt sie erneut (idempotent).
      submittingRef.current = false;
      setSubmitting(false);
      setEditMsg(err.message || "Bewertung fehlgeschlagen");
      return;
    }
    pendingReqId.current = null;   // bestaetigt -> naechste Bewertung bekommt eine neue ID
    const nextResult = { card_id: card.id, rating, kap: card.kap, subname: card.subname, feedback_reason: reviewReason };
    setSession((old) => {
      const q = (old.cards || []).slice();
      const curIdx = old.idx;
      const nextIdx = curIdx + 1;
      // Vaia-Prinzip: schlecht bewertete Karten kommen INNERHALB der Session wieder,
      // damit man sie sofort vertiefen kann (statt nur per FSRS auf Tage rausgeschoben).
      // Nur im Lernmodus, nicht in der zeitbegrenzten Pruefung.
      if (!isExam) {
        if (rating === 1) {
          // "Nochmal" -> in ~4 Karten wieder
          q.splice(Math.min(nextIdx + REQUEUE_AHEAD, q.length), 0, card);
        } else if (rating === 2) {
          // "Schwer" -> am Ende der laufenden Runde nochmal
          q.push(card);
        }
      }
      const done = nextIdx >= q.length;
      const results = [...(old.results || []), nextResult];
      if (done) {
        const elapsedSeconds = isTimedExam ? Math.max(0, (old.minutes || 0) * 60 - secondsLeft) : undefined;
        return { ...old, cards: q, done: true, elapsedSeconds, results };
      }
      return { ...old, cards: q, idx: nextIdx, results };
    });
    // Guard wird beim Kartenwechsel im Reset-Effekt geloest (siehe useEffect auf card?.id).
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
        <h2>{session.mock ? "Volle Prüfung abgeschlossen" : isExam ? "Pruefungsmodus abgeschlossen" : "Tagesabschluss"}</h2>
        {session.mock && (
          session.mockGrading ? <p className="muted">Auswertung läuft…</p>
          : session.mockReport && session.mockReport.composition_missing ? (
            <div className="mock-report fail">
              <div className="mock-report-head"><b>Auswertung nicht möglich</b></div>
              <p>{session.mockReport.verdict}</p>
              <p className="muted mock-rule">Die Prüfungszusammenstellung war nicht mehr im Server (Neustart/abgelaufen), daher lässt sich die Bestehensregel nicht ehrlich prüfen.</p>
              <button className="primary" onClick={() => finish?.()}>Zurück</button>
            </div>
          )
          : session.mockReport ? (
            <div className={`mock-report ${session.mockReport.would_pass ? "pass" : "fail"}`}>
              <div className="mock-report-head">
                <b>{session.mockReport.would_pass ? "✓ Bestanden" : "✗ Nicht bestanden"}</b>
                <span className="mock-overall">{session.mockReport.overall}% gesamt</span>
              </div>
              <p>{session.mockReport.verdict}</p>
              {(session.mockReport.parts || []).map((p) => (
                <div key={p.name} className="mock-part">
                  <span className="mock-part-name">{p.pass ? "✓" : "✗"} {p.name}</span>
                  <div className="mock-part-bar">
                    <i style={{ width: `${Math.min(100, p.pct)}%`, background: p.pass ? "var(--ok)" : "var(--bad)" }} />
                    <em title="50%" />
                  </div>
                  <span className="mock-part-pct">{p.correct}/{p.total} · {p.pct}%</span>
                </div>
              ))}
              <p className="muted mock-rule">Bestehensregel: ≥ 50 % je Teil UND ≥ 50 % gesamt.</p>
              {session.mockReport.composition_missing && (
                <p className="muted mock-rule">Hinweis: Prüfungssitzung nicht mehr im Server – nur beantwortete Karten gewertet.</p>
              )}
            </div>
          ) : session.mockError ? (
            <div className="mock-report fail">
              <p><b>Auswertung fehlgeschlagen.</b> Verbindung prüfen.</p>
              <button className="primary" onClick={() => setSession((old) => ({ ...old, mockError: false }))}>Erneut auswerten</button>
            </div>
          ) : <p className="muted">Auswertung nicht verfügbar.</p>
        )}
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
        {isExam ? (
          <div className="progress"><span style={{ width: `${progress}%` }} /></div>
        ) : (
          <div className="seg-progress" role="progressbar" aria-valuemin={0} aria-valuemax={totalUnique} aria-valuenow={masteredUnique} title={`${masteredUnique}/${totalUnique} gemeistert`}>
            {segments.map((s, i) => <span key={i} className={`seg seg-${s}`} />)}
          </div>
        )}
        <span>{isExam ? `${session.idx + 1}/${cards.length}` : `${masteredUnique}/${totalUnique} gelernt · noch ${remaining}`}</span>
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
          <SourceAnchorPanel anchor={card.source_anchor} />
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
        <SourceAnchorPanel anchor={card.source_anchor} compact={!revealed} />
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
              {[1, 2, 3, 4].map((r) => {
                // Im Lernmodus die Session-Requeue-Wirkung anzeigen (nicht nur das FSRS-Intervall).
                const hint = !isExam && r === 1 ? `in ${REQUEUE_AHEAD + 1} Karten`
                  : !isExam && r === 2 ? "am Ende nochmal"
                  : (preview[r] || "");
                return (
                  <button key={r} className={`rating r${r}`} disabled={submitting} onClick={() => rate(r)}>
                    <b>{RATING_LABELS[r]}</b>
                    <span>{hint}</span>
                  </button>
                );
              })}
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
  const [error, setError] = useState(false);
  function load() {
    setError(false);
    api(`/api/dashboard?module=${encodeURIComponent(module)}`).then(setData).catch(() => setError(true));
  }
  useEffect(() => { setData(null); load(); }, [module]);
  if (!data) return error
    ? <LoadError onRetry={load} label="Dashboard konnte nicht geladen werden." />
    : <div className="loading">Dashboard laedt...</div>;
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

const KNOWLEDGE_STATUS_LABELS = {
  critical: "kritisch",
  shaky: "wackelig",
  building: "im Aufbau",
  secure: "sicher",
  unknown: "offen",
};

function KnowledgeMapPage({ module, startSession, setRoute }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(false);
  const [selectedTopic, setSelectedTopic] = useState("");

  function load() {
    setData(null);
    setError(false);
    setSelectedTopic("");
    api(`/api/knowledge-map?module=${encodeURIComponent(module)}`)
      .then((res) => {
        setData(res);
        setSelectedTopic(res.nodes?.[0]?.topic || "");
      })
      .catch(() => setError(true));
  }
  useEffect(() => { load(); }, [module]);

  if (!data) return error
    ? <LoadError onRetry={load} label="Wissenslandkarte konnte nicht geladen werden." />
    : <div className="loading">Wissenslandkarte laedt...</div>;
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  const route = data.route || [];
  const selected = nodes.find((node) => node.topic === selectedTopic) || nodes[0];
  const connected = selected ? edges.filter((edge) => edge.source === selected.topic || edge.target === selected.topic).slice(0, 8) : [];

  return (
    <section className="knowledge-map-page">
      <div className="panel knowledge-hero">
        <div className="section-head">
          <div>
            <h2>Wissenslandkarte</h2>
            <p>Themen, Abhaengigkeiten und Lernroute bis {formatExamDate(data.exam_date)}.</p>
          </div>
          <Tag size={24} />
        </div>
        <div className="quality-metrics">
          <span><b>{data.summary?.topics || 0}</b> Themen</span>
          <span><b>{data.summary?.critical || 0}</b> kritisch</span>
          <span><b>{data.summary?.shaky || 0}</b> wackelig</span>
          <span><b>{data.summary?.edges || 0}</b> Verbindungen</span>
        </div>
      </div>

      <div className="knowledge-layout">
        <section className="panel knowledge-canvas">
          <div className="section-head">
            <div>
              <h2>Themenknoten</h2>
              <p>Farbe und Score zeigen, wie stabil der Bereich aktuell ist.</p>
            </div>
          </div>
          <div className="knowledge-node-grid">
            {nodes.map((node) => (
              <button
                key={node.topic}
                className={`knowledge-node ${node.status} ${selected?.topic === node.topic ? "active" : ""}`}
                onClick={() => setSelectedTopic(node.topic)}
              >
                <span>{node.chapter_label}</span>
                <b>{node.topic}</b>
                <em>{KNOWLEDGE_STATUS_LABELS[node.status] || node.status} · {node.score}%</em>
                <i><strong style={{ width: `${node.score}%` }} /></i>
              </button>
            ))}
          </div>
        </section>

        <section className="panel knowledge-detail">
          {selected ? (
            <>
              <div className="section-head">
                <div>
                  <h2>{selected.topic}</h2>
                  <p>{selected.chapter_label} · {KNOWLEDGE_STATUS_LABELS[selected.status] || selected.status}</p>
                </div>
                <span className={`knowledge-badge ${selected.status}`}>{selected.score}%</span>
              </div>
              <div className="quality-metrics compact">
                <span><b>{selected.total}</b> Karten</span>
                <span><b>{selected.seen}</b> gesehen</span>
                <span><b>{selected.due}</b> faellig</span>
                <span><b>{selected.needs_review}</b> Review</span>
              </div>
              <div className="knowledge-card-list">
                {(selected.cards || []).map((card) => (
                  <button key={card.id} onClick={() => startSession?.("anki", card.kap)}>
                    <b>VO{card.kap || "?"}</b>
                    <span>{card.title}</span>
                    <em>{card.due ? "faellig" : card.status === "needs_review" ? "Review" : card.source}</em>
                  </button>
                ))}
              </div>
              <div className="button-row-inline">
                <button className="primary" onClick={() => startSession?.("anki", selected.chapters?.[0])}>Knoten lernen</button>
                <button onClick={() => setRoute?.("exam")}>Pruefungsfragen</button>
                <button onClick={() => setRoute?.("workshop")}>Werkstatt</button>
              </div>
              {!!connected.length && (
                <div className="knowledge-connections">
                  <b>Direkte Verbindungen</b>
                  {connected.map((edge) => (
                    <span key={`${edge.source}-${edge.target}-${edge.kind}`}>
                      {edge.source === selected.topic ? edge.target : edge.source}
                      <em>{edge.kind === "dependency" ? edge.label : `${edge.weight} gemeinsame Karten`}</em>
                    </span>
                  ))}
                </div>
              )}
            </>
          ) : <p className="muted">Noch keine Themen gefunden.</p>}
        </section>
      </div>

      <section className="panel knowledge-route">
        <div className="section-head">
          <div>
            <h2>Auto-Lernroute</h2>
            <p>Sortiert nach Risiko, faelligen Karten und Review-Druck.</p>
          </div>
          <button onClick={() => setRoute?.("exam")}>Simulation starten</button>
        </div>
        <div className="route-steps">
          {route.map((step) => (
            <article key={`${step.step}-${step.topic}`}>
              <span>{step.step}</span>
              <div>
                <b>{step.topic}</b>
                <p>{step.action}</p>
                <em>{step.detail}</em>
              </div>
              <button onClick={() => startSession?.("anki", step.kap)} disabled={!step.kap}>Start</button>
            </article>
          ))}
        </div>
      </section>

      <section className="panel knowledge-edge-panel">
        <div className="section-head">
          <div>
            <h2>Querverbindungen</h2>
            <p>Aus gemeinsamen Karten und fachlichen Abhaengigkeiten.</p>
          </div>
        </div>
        <div className="edge-list">
          {edges.slice(0, 16).map((edge) => (
            <span key={`${edge.source}-${edge.target}-${edge.kind}`}>
              <b>{edge.source}</b>
              <i>{edge.kind === "dependency" ? "braucht" : "gemeinsam"}</i>
              <b>{edge.target}</b>
              <em>{edge.label}</em>
            </span>
          ))}
        </div>
      </section>
    </section>
  );
}

function ExamScorePanel({ prognosis }) {
  if (!prognosis) return null;
  return (
    <section className={`panel exam-score-panel ${prognosis.band || ""}`}>
      <div>
        <h2>Pruefungsreife</h2>
        <p>{prognosis.next_step}</p>
      </div>
      <div className="forecast-score compact"><b>{prognosis.overall || 0}%</b><span>{prognosis.band_label || "gesamt"}</span></div>
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
      {!!prognosis.blockers?.length && (
        <div className="exam-blockers">
          <b>Naechste Blocker</b>
          {prognosis.blockers.slice(0, 4).map((item) => (
            <span key={item.key}>{item.label}<em>{item.detail}</em></span>
          ))}
        </div>
      )}
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
  const examDate = formatExamDate(plan.exam_date);
  return (
    <section className="panel final-plan">
      <div className="section-head">
        <div>
          <h2>7-Tage-Endspurtplan</h2>
          <p>{plan.rule}</p>
        </div>
        <span className="deck-pill">bis {examDate}</span>
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
  const examDate = formatExamDate(plan.exam_date);
  return (
    <section className="panel weekly-plan">
      <div className="section-head">
        <div>
          <h2>Wochenansicht bis {examDate}</h2>
          <p>{plan.rule}</p>
        </div>
        <span className="deck-pill">{examDate}</span>
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

  function applyAnswerReview() {
    if (!question) return;
    const review = answerRubricReview(answers[question.card_id] || "", question);
    setScores((old) => ({
      ...old,
      [question.card_id]: { ...(old[question.card_id] || {}), ...review.subScores },
    }));
    setChecklist((old) => ({
      ...old,
      [question.card_id]: Array.from(new Set([...(old[question.card_id] || []), ...review.checklist])),
    }));
    setErrorTypes((old) => ({
      ...old,
      [question.card_id]: Array.from(new Set([...(old[question.card_id] || []), ...review.errorTypes])),
    }));
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
      results: (exam.questions || []).map((q) => {
        const review = answerRubricReview(answers[q.card_id] || "", q);
        return {
          card_id: q.card_id,
          sub_scores: (q.subquestions || []).map((sub) => (scores[q.card_id] || {})[sub.id] || review.subScores[sub.id] || "miss"),
          confidence: confidence[q.card_id] || "",
          error_types: Array.from(new Set([...(errorTypes[q.card_id] || []), ...review.errorTypes])),
          auto_score: review.score,
          auto_missing_terms: review.missingTerms.slice(0, 12),
          auto_checklist: review.checklist,
          answer_note: [
            answers[q.card_id] || "",
            (checklist[q.card_id] || []).length ? `Checkliste: ${(checklist[q.card_id] || []).map(checklistLabel).join(", ")}` : "",
            `Auto-Check: ${review.label}, ${review.score}% Abdeckung`,
            review.missingTerms.length ? `Fehlt: ${review.missingTerms.slice(0, 8).join(", ")}` : "",
          ].filter(Boolean).join("\n\n"),
        };
      }),
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
  const currentReview = answerRubricReview(currentAnswer, question);
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
        <SourceAnchorPanel anchor={question.source_anchor} />
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
        {!!currentAnswer.trim() && (
          <div className={`answer-review-panel ${currentReview.confidenceHint}`}>
            <div className="answer-review-head">
              <div>
                <h3>Antwortpruefung 2.0</h3>
                <p>Automatischer Rubrik-Check aus Musterantwort, Punkteschema und deiner Antwort.</p>
              </div>
              <span><b>{currentReview.score}%</b>{currentReview.label}</span>
            </div>
            <div className="answer-review-grid">
              {currentReview.categories.map((item) => (
                <article key={item.id}>
                  <b>{item.category}</b>
                  <p>{item.prompt}</p>
                  <span className={item.score}>{item.score === "full" ? "voll" : item.score === "partial" ? "teilweise" : "fehlt"}</span>
                  {!!item.missing.length && <em>Fehlt: {item.missing.slice(0, 4).join(", ")}</em>}
                </article>
              ))}
            </div>
            <div className="answer-review-footer">
              <div>
                <b>Fehlende Bausteine</b>
                {currentReview.missingChecklist.length
                  ? currentReview.missingChecklist.map((item) => <span key={item.key}>{item.label}</span>)
                  : <span>Keine harte Luecke sichtbar</span>}
              </div>
              <div>
                <b>Diagnose</b>
                {currentReview.errorTypes.length
                  ? currentReview.errorTypes.map((key) => <span key={key}>{EXAM_ERROR_TYPES.find(([item]) => item === key)?.[1] || key}</span>)
                  : <span>Antwort wirkt pruefungsnah</span>}
              </div>
              <button onClick={applyAnswerReview}>Vorschlag uebernehmen</button>
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
  const voiceText = [
    `Frage ${idx + 1}: ${stripHtmlText(question?.question || "")}`,
    ...shownPrompts.map((prompt) => `${prompt.label}: ${prompt.prompt}`),
  ].join(" ");
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
        <VoiceExamControls
          readText={voiceText}
          value={currentAnswer}
          onValue={(next) => setAnswers((old) => ({ ...old, [currentKey]: next }))}
        />
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

function ExamPage({ startExam, startMockExam, startSession, module }) {
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
            <p>Schriftliche Antwortpruefung mit Rubrik-Check, Musterantwort, Fehlerdiagnose und Formeltraining.</p>
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

      <section className="panel mock-exam-panel">
        <div className="section-head">
          <div>
            <h2>Volle Prüfung (Mock-Exam)</h2>
            <p>Über alle Teile balanciert, mit Zeitlimit. Am Ende: Bestehen/Durchfallen nach der echten Regel (≥ 50 % je Teil UND gesamt) mit Teil-Auswertung.</p>
          </div>
          <button className="primary" onClick={() => startMockExam?.()}><Target size={16} /> Prüfung starten</button>
        </div>
      </section>

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

  // Jede Aenderung an den Importoptionen verwirft die Vorschau, sonst wuerde beim Import
  // das aktuelle payload verwendet und koennte von der gezeigten Vorschau abweichen.
  // Der Import-Button ist an preview?.valid gebunden und wird dadurch bis zur
  // Neuberechnung gesperrt.
  useEffect(() => {
    setPreview(null);
  }, [format, source, defaultKap, dedupe, text, module]);

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
            <textarea value={text} onChange={(e) => setText(e.target.value)} rows={14} />
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

function fmtChangeDate(iso) {
  if (!iso) return "unbearbeitet";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unbearbeitet";
  return d.toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function CardReviewPage({ onDone, module }) {
  const [status, setStatus] = useState("needs_review");
  const [kap, setKap] = useState("");
  const [tag, setTag] = useState("");
  const [media, setMedia] = useState("all");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("default");
  const [data, setData] = useState({ cards: [], summary: {} });
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    const qs = new URLSearchParams({ status, limit: "80", module, sort });
    if (kap) qs.set("kap", kap);
    if (tag) qs.set("tag", tag);
    if (media !== "all") qs.set("media", media);
    if (query) qs.set("q", query);
    const res = await api(`/api/cards?${qs}`);
    setData(res);
    setSelected(res.cards?.[0] || null);
  }
  useEffect(() => { load().catch(() => {}); }, [status, kap, tag, media, sort, module]);

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
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="default">Sortierung: Standard</option>
            <option value="updated">Zuletzt geaendert</option>
            <option value="updated_asc">Aeltest geaendert</option>
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
              <b>VO{card.kap} · {card.status} · <span className="card-change-date">geaendert {fmtChangeDate(card.updated_at)}</span></b>
              <em>{[(card.tags || []).join(" · "), card.has_photo ? "Foto" : "", card.photo_recommended ? "Foto empfohlen" : "", card.sketch_required ? "Skizze" : ""].filter(Boolean).join(" · ")}</em>
              <span dangerouslySetInnerHTML={{ __html: card.q }} />
            </button>
          ))}
        </div>
      </div>
      <div className="panel quality-editor">
        {selected ? (
          <>
            <p className="muted card-change-date">Zuletzt geaendert: {fmtChangeDate(selected.updated_at)}</p>
            <SourceAnchorPanel anchor={selected.source_anchor} />
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
            <SourceAnchorPanel anchor={selected.source_anchor} />
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
            <SourceAnchorPanel anchor={draft.source_anchor} />
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

function SourceAuditPanel({ module, setRoute }) {
  const [audit, setAudit] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    setMsg("");
    try {
      setAudit(await api(`/api/source-audit?module=${encodeURIComponent(module)}&limit=8`));
    } catch (err) {
      setMsg(err.message || "Quellen-Audit fehlgeschlagen");
    }
  }

  useEffect(() => { load().catch(() => {}); }, [module]);
  return (
    <div className="panel source-audit-panel">
      <div className="section-head">
        <div>
          <h3>Quellenmodus</h3>
          <p>{audit ? `Durchschnitt ${audit.avg_score}% · ${audit.weak || 0} schwache Quellen` : "Skriptanker und Herleitung jeder Karte pruefen."}</p>
        </div>
        <button onClick={load}><RefreshCw size={16} /> Aktualisieren</button>
      </div>
      {audit && (
        <>
          <div className="source-audit-metrics">
            <span><b>{audit.strong || 0}</b> gruen</span>
            <span><b>{audit.medium || 0}</b> gelb</span>
            <span><b>{audit.weak || 0}</b> rot</span>
          </div>
          <div className="source-audit-list">
            {(audit.items || []).map((item) => (
              <button key={item.card.id} onClick={() => setRoute?.("workshop")}>
                <b>VO{item.card.kap} · {item.anchor.score}%</b>
                <span>{item.card.title}</span>
                <em>{(item.anchor.issues || []).join(" · ") || item.anchor.source}</em>
              </button>
            ))}
            {!(audit.items || []).length && <p className="muted">Keine roten Quellenanker im Audit.</p>}
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
        <SourceAuditPanel module={module} setRoute={setRoute} />
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
              {/* class card-photo: der globale Lightbox-Handler auf .wrap reagiert darauf */}
              <img className="card-photo" src={photo.url} alt={photo.filename} />
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

function FehlerbuchPage({ module, startSession }) {
  const [data, setData] = useState(null);
  const [showResolved, setShowResolved] = useState(false);
  const [explain, setExplain] = useState({});
  const [diagnosis, setDiagnosis] = useState(null);
  const [busy, setBusy] = useState("");
  const [coach, setCoach] = useState(false);
  const [error, setError] = useState(false);

  async function load() {
    setError(false);
    try { setData(await api(`/api/fehlerbuch?module=${module}&include_resolved=${showResolved}`)); }
    catch (err) { setError(true); }
  }
  useEffect(() => { setData(null); load(); }, [module, showResolved]);
  useEffect(() => { api("/api/coach/status").then((s) => setCoach(!!s.available)).catch(() => {}); }, []);

  async function resolve(cardId) {
    await api(`/api/fehlerbuch/${encodeURIComponent(cardId)}/resolve`, { method: "POST" });
    load().catch(() => {});
  }
  async function doExplain(cardId) {
    setBusy(cardId);
    try {
      const res = await api("/api/coach/explain", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: cardId }),
      });
      setExplain((old) => ({ ...old, [cardId]: res.explanation }));
    } catch (err) {
      setExplain((old) => ({ ...old, [cardId]: `Coach nicht verfuegbar: ${err.message}` }));
    } finally { setBusy(""); }
  }
  async function runDiagnosis() {
    setBusy("diag");
    try {
      const res = await api("/api/coach/error-diagnosis", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ module }),
      });
      setDiagnosis(res);
    } catch (err) {
      setDiagnosis({ diagnosis: `Diagnose fehlgeschlagen: ${err.message}`, offline: true });
    } finally { setBusy(""); }
  }

  if (!data) return error
    ? <LoadError onRetry={load} label="Fehlerbuch konnte nicht geladen werden." />
    : <div className="loading">Fehlerbuch laedt...</div>;
  const s = data.summary || {};
  const entries = data.entries || [];
  return (
    <section className="panel">
      <div className="section-head">
        <div>
          <h2><AlertTriangle size={18} /> Fehlerbuch</h2>
          <p>{s.open || 0} offen · {s.resolved || 0} erledigt · {s.total || 0} gesamt</p>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <button onClick={() => setShowResolved((v) => !v)}>{showResolved ? "Nur offene" : "Auch erledigte"}</button>
          <button onClick={runDiagnosis} disabled={busy === "diag"}>
            <Brain size={16} /> {busy === "diag" ? "Analysiere..." : "Fehler-Diagnose"}
          </button>
        </div>
      </div>
      {diagnosis && (
        <div className="panel" style={{ background: "var(--surface-2, #f4f6f8)", marginBottom: 12 }}>
          <b>Diagnose {diagnosis.offline ? "(offline)" : "(KI)"}</b>
          <pre style={{ whiteSpace: "pre-wrap", margin: "6px 0 0", fontFamily: "inherit" }}>{diagnosis.diagnosis}</pre>
        </div>
      )}
      {!entries.length && <p className="muted">Kein offener Fehler. Sauber! 🎉</p>}
      {entries.map((e) => (
        <div key={e.card_id} className="panel" style={{ marginBottom: 10, opacity: e.resolved_at ? 0.6 : 1 }}>
          <div className="section-head">
            <div>
              <b>VO{e.kap} · {e.miss_count}× verfehlt · {e.source === "exam" ? "Pruefung" : "Trainer"}</b>
              <p style={{ margin: "4px 0" }}>{e.title}</p>
            </div>
            <div style={{ display: "flex", gap: 6 }}>
              {coach && <button onClick={() => doExplain(e.card_id)} disabled={busy === e.card_id}>
                <Sparkles size={14} /> {busy === e.card_id ? "..." : "Erklaeren"}
              </button>}
              {!e.resolved_at && <button className="primary" onClick={() => resolve(e.card_id)}><Check size={14} /> Erledigt</button>}
            </div>
          </div>
          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
            {(e.points || []).slice(0, 4).map((p, i) => <li key={i}>{p}</li>)}
          </ul>
          {explain[e.card_id] && (
            <div style={{ marginTop: 8, padding: 8, borderLeft: "3px solid var(--accent, #06c)" }}>
              <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontFamily: "inherit" }}>{explain[e.card_id]}</pre>
            </div>
          )}
        </div>
      ))}
    </section>
  );
}

function AnalyticsPage({ module }) {
  const [items, setItems] = useState(null);
  const [insights, setInsights] = useState(null);
  const [error, setError] = useState(false);
  function load() {
    setError(false);
    Promise.all([
      api(`/api/item-analytics?module=${module}`).then(setItems),
      api(`/api/fsrs-insights?module=${module}`).then(setInsights),
    ]).catch(() => setError(true));
  }
  useEffect(() => { setItems(null); setInsights(null); load(); }, [module]);
  if (!items || !insights) return error
    ? <LoadError onRetry={load} label="Analytics konnte nicht geladen werden." />
    : <div className="loading">Analytics laedt...</div>;
  const maxF = Math.max(1, ...insights.forecast.map((f) => f.count));
  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><Gauge size={18} /> Analytics</h2>
          <p>{items.cards_reviewed}/{items.cards_total} Karten geuebt · Trefferquote {items.overall_hit_rate}% · Retention {insights.retention_pct ?? "–"}%</p></div>
      </div>
      <h3>Faellig – naechste 14 Tage</h3>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 3, height: 90, margin: "8px 0 16px" }}>
        {insights.forecast.map((f) => (
          <div key={f.date} title={`${f.date}: ${f.count}`} style={{ flex: 1, textAlign: "center" }}>
            <div style={{ height: `${(f.count / maxF) * 70}px`, background: "var(--accent, #06c)", borderRadius: 3, minHeight: f.count ? 3 : 0 }} />
            <small style={{ fontSize: 9 }}>{f.date.slice(8)}</small>
          </div>
        ))}
      </div>
      <div className="source-audit-metrics" style={{ marginBottom: 14 }}>
        <span><b>{insights.overdue}</b> ueberfaellig</span>
        <span><b>{insights.new}</b> neu</span>
        {insights.stability_buckets.map((b) => <span key={b.label}><b>{b.count}</b> {b.label}</span>)}
      </div>
      <h3>Schwerste Karten</h3>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
          <thead><tr style={{ textAlign: "left", borderBottom: "1px solid #ccc" }}>
            <th>Karte</th><th>VO</th><th>Quote</th><th>Reviews</th><th>Nochmal</th></tr></thead>
          <tbody>
            {items.worst.slice(0, 25).map((it) => (
              <tr key={it.card_id} style={{ borderBottom: "1px solid var(--line)" }}>
                <td>{it.title}</td><td>{it.kap}</td>
                <td style={{ color: (it.hit_rate ?? 100) < 60 ? "var(--bad)" : "inherit" }}>{it.hit_rate ?? "–"}%</td>
                <td>{it.reviews}</td><td>{it.agains}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function StudyPlanPage({ module, startSession, startExam, setRoute }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(false);
  function load() { setError(false); api(`/api/study-plan?module=${module}`).then(setD).catch(() => setError(true)); }
  useEffect(() => { setD(null); load(); }, [module]);
  if (!d) return error
    ? <LoadError onRetry={load} label="Lernplan konnte nicht geladen werden." />
    : <div className="loading">Lernplan laedt...</div>;

  const runTask = (t) => {
    if (t.kind === "review") startSession?.("anki");
    else if (t.kind === "new") startSession?.("anki", t.kap || null);
    else if (t.kind === "exam") startExam?.(t.count || 10, "weak");
    else if (t.kind === "mock") startExam?.(t.count || 20, "mixed");
    else if (t.kind === "fehlerbuch") setRoute?.("fehlerbuch");
  };
  const phaseColor = { aufbau: "#2980b9", festigen: "var(--warn-strong)", pruefung: "var(--bad)" }[d.phase?.key] || "var(--muted)";

  return (
    <section className="study-plan">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2>Lernplan</h2>
            <p>Adaptiver Plan bis zur Prüfung – jedes Mal neu aus deinem aktuellen Stand berechnet.</p>
          </div>
          <div className="forecast-score compact"><b>{d.overall}%</b><span>Reife</span></div>
        </div>
        <div className="plan-meta">
          <span className="plan-phase" style={{ background: phaseColor }}>{d.phase?.label}</span>
          <span><b>{d.days_left}</b> Tage bis {new Date(d.exam_date).toLocaleDateString("de-AT")}</span>
          <span className="muted">{d.phase?.focus}</span>
        </div>
        <div className="plan-capacity">
          <div><b>{d.capacity?.new_per_day}</b><span>neue Karten / Tag</span></div>
          <div><b>{d.capacity?.reviews_per_day}</b><span>Wiederholungen / Tag</span></div>
          <div><b>{d.capacity?.unseen}</b><span>ungesehen</span></div>
          <div><b>{d.capacity?.due}</b><span>fällig</span></div>
        </div>
      </div>

      <div className="panel">
        <h3>Heute</h3>
        <div className="plan-today">
          {(d.today || []).length === 0 && (
            <p className="muted">Heute nichts Dringendes – halte deine Wiederholungen am Laufen.</p>
          )}
          {(d.today || []).map((t) => (
            <button key={t.key} className="plan-task" onClick={() => runTask(t)}>
              <div>
                <b>{t.title}</b>
                {t.detail && <span className="muted">{t.detail}</span>}
              </div>
              <span className="plan-task-go">Start →</span>
            </button>
          ))}
        </div>
      </div>

      <div className="panel">
        <h3>Teile – Schwächstes zuerst</h3>
        {(d.parts || []).map((p) => (
          <div key={p.name} className={`plan-part${p.focus ? " focus" : ""}`}>
            <div className="plan-part-head">
              <b>{p.focus ? "⚠ " : ""}{p.name}</b>
              <span>{p.score}%</span>
            </div>
            <div className="plan-part-bar">
              <i style={{ width: `${Math.min(100, p.score)}%`, background: p.focus ? "var(--bad)" : "var(--ok)" }} />
            </div>
            <span className="muted">
              {p.coverage}% gesehen
              {p.accuracy !== null && ` · ${p.accuracy}% richtig`}
              {p.unseen > 0 && ` · ${p.unseen} neu`}
              {p.due > 0 && ` · ${p.due} fällig`}
            </span>
          </div>
        ))}
      </div>

      <div className="panel">
        <h3>Fahrplan bis zur Prüfung</h3>
        {(d.schedule || []).length === 0 && <p className="muted">Prüfung ist da – viel Erfolg!</p>}
        <div className="plan-schedule">
          {(d.schedule || []).map((s) => (
            <div key={s.date} className={`plan-day kind-${s.kind}`}>
              <div className="plan-day-date">
                <b>{s.weekday}</b>
                <span>{new Date(s.date).toLocaleDateString("de-AT", { day: "2-digit", month: "2-digit" })}</span>
              </div>
              <div className="plan-day-body">
                <b>{s.theme}</b>
                <span className="muted">{s.new > 0 ? `${s.new} neu · ` : ""}{s.reviews} Wdh · T-{s.days_left}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function ReadinessPage({ module, startExam, setRoute, startSession }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(false);
  function load() { setError(false); api(`/api/readiness-plan?module=${module}`).then(setD).catch(() => setError(true)); }
  useEffect(() => { setD(null); load(); }, [module]);
  if (!d) return error
    ? <LoadError onRetry={load} label="Reifeplan konnte nicht geladen werden." />
    : <div className="loading">Reifeplan laedt...</div>;
  const bandColor = { ready: "var(--ok)", steady: "var(--warn-strong)", risk: "var(--bad)" }[d.band] || "var(--muted)";
  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><CalendarClock size={18} /> Reifeplan</h2>
          <p>{d.days_left} Tage bis zur Pruefung</p></div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontSize: 30, fontWeight: 700, color: bandColor }}>{d.overall}%</div>
          <small>Pruefungsreife</small>
        </div>
      </div>
      <div className="source-audit-metrics">
        <span><b>{d.daily_reviews}</b> Karten/Tag empfohlen</span>
        <span><b>{d.daily_new}</b> neue/Tag</span>
        <span><b>{d.unseen}</b> ungesehen</span>
        <span><b>{d.open_mistakes}</b> offene Fehler</span>
      </div>
      {d.pass_prediction && (
        <div style={{ marginTop: 16, padding: 12, borderRadius: 8,
          background: d.pass_prediction.would_pass ? "var(--ok-bg)" : "var(--bad-bg)",
          border: `1px solid ${d.pass_prediction.would_pass ? "var(--ok)" : "var(--bad)"}` }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <b style={{ color: d.pass_prediction.would_pass ? "var(--ok)" : "var(--bad)" }}>
              {d.pass_prediction.would_pass ? "✓ Aktuell auf Bestehenskurs" : "✗ Noch nicht bestehenssicher"}
            </b>
            <small className="muted">{d.pass_prediction.rule}</small>
          </div>
          <p style={{ margin: "6px 0 10px", fontSize: 14 }}>{d.pass_prediction.verdict}</p>
          {(d.pass_prediction.parts || []).map((p) => (
            <div key={p.name} style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}>
              <span style={{ width: 18 }}>{p.pass ? "✓" : "✗"}</span>
              <span style={{ flex: 1 }}>
                {p.name}
                {p.accuracy_blocks && (
                  <em style={{ color: "var(--bad)", fontStyle: "normal", fontSize: 12 }}> · nur {p.accuracy}% richtig beantwortet</em>
                )}
              </span>
              <div style={{ flex: 1, background: "var(--panel-line)", borderRadius: 5, height: 8, position: "relative" }}>
                <div style={{ width: `${Math.min(100, p.score)}%`, height: "100%", borderRadius: 5,
                  background: p.pass ? "var(--ok)" : "var(--bad)" }} />
                <div style={{ position: "absolute", left: "50%", top: -2, bottom: -2, width: 1, background: "var(--muted)" }} title="50%" />
              </div>
              <span style={{ width: 42, textAlign: "right", color: p.pass ? "var(--ok)" : "var(--bad)" }}>{p.score}%</span>
              <button className="teil-uben" onClick={() => startSession?.("anki", null, p.name)} title={`${p.name} gezielt üben`}>üben</button>
            </div>
          ))}
          <small className="muted">Gestrichelte Linie = 50-%-Bestehensgrenze je Teil. Klick auf „üben" startet eine Session nur aus diesem Teil.</small>
        </div>
      )}
      <h3 style={{ marginTop: 16 }}>Fokus-Blöcke</h3>
      {(d.milestones || []).map((m) => (
        <div key={m.block} style={{ display: "flex", justifyContent: "space-between", padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <span><b>{m.block}</b> — {m.action}</span>
          <span style={{ color: { ready: "var(--ok)", steady: "var(--warn-strong)", risk: "var(--bad)" }[m.status] || "var(--muted)" }}>{m.score}%</span>
        </div>
      ))}
      <div style={{ marginTop: 14, display: "flex", gap: 8 }}>
        <button className="primary" onClick={() => startExam?.(12, "weak")}><Target size={16} /> Schwaechen-Pruefung</button>
        <button onClick={() => setRoute?.("home")}>Zum Trainer</button>
      </div>
    </section>
  );
}

function LastMinutePage({ module }) {
  const [d, setD] = useState(null);
  const [error, setError] = useState(false);
  function load() { setError(false); api(`/api/last-minute-sheet?module=${module}`).then(setD).catch(() => setError(true)); }
  useEffect(() => { setD(null); load(); }, [module]);
  if (!d) return error
    ? <LoadError onRetry={load} label="Spickzettel konnte nicht geladen werden." />
    : <div className="loading">Spickzettel laedt...</div>;
  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><ListChecks size={18} /> Last-Minute-Spickzettel</h2>
          <p>Kernaussagen der schwaechsten Kapitel zuerst</p></div>
        <button onClick={() => window.print()}>Drucken</button>
      </div>
      {(d.chapters || []).map((ch) => (
        <div key={ch.kap} style={{ marginBottom: 14 }}>
          <h3 style={{ marginBottom: 4 }}>{ch.name}</h3>
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {ch.facts.map((f, i) => <li key={i}><b>{f.title}:</b> {f.point}</li>)}
          </ul>
        </div>
      ))}
      {!(d.chapters || []).length && <p className="muted">Noch keine Daten.</p>}
    </section>
  );
}

function QuestsPage({ module }) {
  const [d, setD] = useState(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState(false);
  async function load() {
    setError(false);
    try { setD(await api(`/api/gamification?module=${module}`)); }
    catch (err) { setError(true); }
  }
  useEffect(() => { setD(null); load(); }, [module]);
  async function claim(key) {
    setMsg("");
    try {
      const res = await api("/api/gamification/quests/claim", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ key, module }),
      });
      setMsg(res.ok ? `+${res.awarded} XP!` : "Bereits abgeholt.");
      load().catch(() => {});
    } catch (err) { setMsg(err.message); }
  }
  if (!d) return error
    ? <LoadError onRetry={load} label="Quests konnten nicht geladen werden." />
    : <div className="loading">Quests laden...</div>;
  const xp = d.xp || {};
  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><Trophy size={18} /> Quests & Fortschritt</h2>
          <p>Level {xp.level} · {xp.rank} · <Flame size={13} /> {d.streak?.current || 0} Tage Streak</p></div>
        <div style={{ textAlign: "right" }}><b>{xp.total_xp} XP</b></div>
      </div>
      <div style={{ background: "var(--panel-line)", borderRadius: 6, height: 10, margin: "6px 0 4px", overflow: "hidden" }}>
        <div style={{ width: `${xp.progress_pct || 0}%`, height: "100%", background: "var(--accent, #06c)" }} />
      </div>
      <small className="muted">{xp.xp_in_level}/{xp.next_level_xp} bis Level {xp.level + 1}</small>
      {msg && <div className="form-msg">{msg}</div>}
      <h3 style={{ marginTop: 16 }}>Quests</h3>
      {(d.quests || []).map((q) => (
        <div key={q.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: "1px solid var(--line)" }}>
          <div style={{ flex: 1 }}>
            <b>{q.title}</b>
            <div style={{ background: "var(--panel-line)", borderRadius: 5, height: 7, marginTop: 4 }}>
              <div style={{ width: `${Math.min(100, (q.progress / q.goal) * 100)}%`, height: "100%", background: q.done ? "var(--ok)" : "var(--accent, #06c)", borderRadius: 5 }} />
            </div>
            <small className="muted">{q.progress}/{q.goal} · +{q.xp} XP</small>
          </div>
          {q.claimed ? <span style={{ color: "var(--ok)" }}><Check size={16} /> abgeholt</span>
            : q.done ? <button className="primary" onClick={() => claim(q.key)}>Abholen</button>
            : <span className="muted">offen</span>}
        </div>
      ))}
      <h3 style={{ marginTop: 16 }}>Abzeichen</h3>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
        {(d.badges || []).map((b) => (
          <span key={b.key} style={{ padding: "6px 10px", borderRadius: 16, fontSize: 13,
            background: b.earned ? "var(--ok)" : "var(--panel-line)", color: b.earned ? "#fff" : "var(--muted)" }}>
            <Award size={13} /> {b.label}
          </span>
        ))}
      </div>
    </section>
  );
}

function ProcessTrainerPage({ module }) {
  const [list, setList] = useState(null);
  const [error, setError] = useState(false);
  const [idx, setIdx] = useState(0);
  const [order, setOrder] = useState([]);
  const [result, setResult] = useState(null);
  const [score, setScore] = useState({ correct: 0, done: 0 });
  const [busy, setBusy] = useState(false);

  function load() {
    setError(false);
    api(`/api/processes?module=${module}`)
      .then((d) => {
        const procs = d.processes || [];
        setList(procs); setIdx(0); setOrder(procs[0]?.steps || []);
        setResult(null); setScore({ correct: 0, done: 0 });
      })
      .catch(() => setError(true));
  }
  useEffect(() => { setList(null); load(); }, [module]);

  if (!list) return error
    ? <LoadError onRetry={load} label="Prozesstrainer konnte nicht geladen werden." />
    : <div className="loading">Prozesstrainer laedt...</div>;
  if (!list.length) return <section className="panel"><p className="muted">Keine Prozesse für dieses Modul.</p></section>;

  const p = list[idx];
  function move(i, dir) {
    if (result) return;
    const j = i + dir;
    if (j < 0 || j >= order.length) return;
    const nextOrder = order.slice();
    [nextOrder[i], nextOrder[j]] = [nextOrder[j], nextOrder[i]];
    setOrder(nextOrder);
  }
  async function checkAnswer() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await api("/api/processes/check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: p.id, order: order.map((s) => s.sid) }),
      });
      setResult(res);
      setScore((s) => ({ correct: s.correct + (res.correct ? 1 : 0), done: s.done + 1 }));
    } catch (e) { setResult({ error: true }); } finally { setBusy(false); }
  }
  function next() {
    if (idx + 1 >= list.length) { load(); return; }
    const ni = idx + 1;
    setIdx(ni); setOrder(list[ni].steps || []); setResult(null);
  }

  return (
    <section className="process-trainer">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2><ListOrdered size={20} /> Prozesstrainer</h2>
            <p>Bring die Schritte des Prozesses in die richtige Reihenfolge.</p>
          </div>
          <div className="forecast-score compact"><b>{score.correct}/{score.done}</b><span>richtig</span></div>
        </div>
        <div className="reaction-progress">Prozess {idx + 1} / {list.length} · {p.teil}</div>
        <h3>{p.name}</h3>
        {p.note && <p className="muted">{p.note}</p>}
        <ol className="process-steps">
          {order.map((s, i) => {
            const posClass = result && !result.error ? (result.positions_ok[i] ? "ok" : "bad") : "";
            return (
              <li key={s.sid} className={`process-step ${posClass}`}>
                <span className="process-step-num">{i + 1}</span>
                <span className="process-step-text">{s.text}</span>
                {!result && (
                  <span className="process-step-actions">
                    <button type="button" disabled={i === 0} onClick={() => move(i, -1)} aria-label="nach oben">↑</button>
                    <button type="button" disabled={i === order.length - 1} onClick={() => move(i, 1)} aria-label="nach unten">↓</button>
                  </span>
                )}
              </li>
            );
          })}
        </ol>
        {!result && <button className="primary" disabled={busy} onClick={checkAnswer}>Prüfen</button>}
        {result && result.error && (
          <div className="reaction-result form"><p>Prüfung fehlgeschlagen. Verbindung prüfen.</p>
            <button onClick={() => setResult(null)}>Nochmal</button></div>
        )}
        {result && !result.error && (
          <div className={`reaction-result ${result.correct ? "ok" : "bad"}`}>
            <p><b>{result.correct ? "✓ Richtige Reihenfolge!" : `✗ ${result.n_correct}/${result.n_total} an der richtigen Stelle.`}</b></p>
            {!result.correct && (
              <>
                <p className="muted">Richtige Reihenfolge:</p>
                <ol className="process-solution">
                  {result.correct_steps.map((t, i) => <li key={i}>{t}</li>)}
                </ol>
              </>
            )}
            <button className="primary" onClick={next}>Nächster Prozess →</button>
          </div>
        )}
      </div>
    </section>
  );
}

function ConfusionTrainerPage({ module }) {
  const [list, setList] = useState(null);
  const [error, setError] = useState(false);
  const [idx, setIdx] = useState(0);
  const [result, setResult] = useState(null);
  const [score, setScore] = useState({ correct: 0, done: 0 });
  const [busy, setBusy] = useState(false);

  function load() {
    setError(false);
    api(`/api/confusions?module=${module}`)
      .then((d) => { setList(d.items || []); setIdx(0); setResult(null); setScore({ correct: 0, done: 0 }); })
      .catch(() => setError(true));
  }
  useEffect(() => { setList(null); load(); }, [module]);

  if (!list) return error
    ? <LoadError onRetry={load} label="Verwechslungs-Trainer konnte nicht geladen werden." />
    : <div className="loading">Verwechslungs-Trainer laedt...</div>;
  if (!list.length) return <section className="panel"><p className="muted">Keine Fragen für dieses Modul.</p></section>;

  const q = list[idx];
  async function choose(key) {
    if (result || busy) return;
    setBusy(true);
    try {
      const res = await api("/api/confusions/check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ item_id: q.item_id, choice: key }),
      });
      setResult({ ...res, chosen: key });
      setScore((s) => ({ correct: s.correct + (res.correct ? 1 : 0), done: s.done + 1 }));
    } catch (e) { setResult({ error: true }); } finally { setBusy(false); }
  }
  function next() {
    if (idx + 1 >= list.length) { load(); return; }
    setIdx(idx + 1); setResult(null);
  }

  return (
    <section className="confusion-trainer">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2><Split size={20} /> Verwechslungs-Trainer</h2>
            <p>Häufig verwechselte Begriffe – welcher ist gemeint?</p>
          </div>
          <div className="forecast-score compact"><b>{score.correct}/{score.done}</b><span>richtig</span></div>
        </div>
        <div className="reaction-progress">Frage {idx + 1} / {list.length} · {q.teil}</div>
        <p className="confusion-statement">{q.statement}</p>
        <div className="confusion-options">
          {q.options.map((o) => {
            let cls = "";
            if (result && !result.error) {
              if (o.key === result.correct_key) cls = "ok";
              else if (o.key === result.chosen) cls = "bad";
            }
            return (
              <button key={o.key} className={`confusion-option ${cls}`} disabled={!!result} onClick={() => choose(o.key)}>
                {o.label}
              </button>
            );
          })}
        </div>
        {result && result.error && (
          <div className="reaction-result form"><p>Prüfung fehlgeschlagen. Verbindung prüfen.</p>
            <button onClick={() => setResult(null)}>Nochmal</button></div>
        )}
        {result && !result.error && (
          <div className={`reaction-result ${result.correct ? "ok" : "bad"}`}>
            <p><b>{result.correct ? "✓ Richtig!" : `✗ Richtig wäre: ${result.correct_label}`}</b></p>
            {result.explain && <p className="muted">{result.explain}</p>}
            <button className="primary" onClick={next}>Nächste Frage →</button>
          </div>
        )}
      </div>
    </section>
  );
}

function ReactionTrainerPage({ module }) {
  const [list, setList] = useState(null);
  const [error, setError] = useState(false);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [showHint, setShowHint] = useState(false);
  const [score, setScore] = useState({ correct: 0, done: 0 });
  const [busy, setBusy] = useState(false);

  function load() {
    setError(false);
    api(`/api/reactions?module=${module}`)
      .then((d) => {
        const shuffled = [...(d.reactions || [])].sort(() => Math.random() - 0.5);
        setList(shuffled); setIdx(0); setAnswer(""); setResult(null); setShowHint(false);
        setScore({ correct: 0, done: 0 });
      })
      .catch(() => setError(true));
  }
  useEffect(() => { setList(null); load(); }, [module]);

  if (!list) return error
    ? <LoadError onRetry={load} label="Reaktionstrainer konnte nicht geladen werden." />
    : <div className="loading">Reaktionstrainer laedt...</div>;
  if (!list.length) return <section className="panel"><p className="muted">Keine Reaktionen für dieses Modul.</p></section>;

  const r = list[idx];

  async function checkAnswer() {
    if (!answer.trim() || busy) return;
    setBusy(true);
    try {
      const res = await api("/api/reactions/check", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ id: r.id, answer }),
      });
      setResult(res);
      if (!res.form_error) setScore((s) => ({ correct: s.correct + (res.correct ? 1 : 0), done: s.done + 1 }));
    } catch (e) {
      setResult({ form_error: true, message: "Prüfung fehlgeschlagen. Verbindung prüfen." });
    } finally { setBusy(false); }
  }
  function next() {
    if (idx + 1 >= list.length) { load(); return; }  // durch -> neu mischen
    setIdx(idx + 1); setAnswer(""); setResult(null); setShowHint(false);
  }

  return (
    <section className="reaction-trainer">
      <div className="panel">
        <div className="section-head">
          <div>
            <h2><FlaskConical size={20} /> Reaktionstrainer</h2>
            <p>Schreib die Reaktionsgleichung. Koeffizienten musst du nicht exakt treffen – es zählen Edukte und Produkte.</p>
          </div>
          <div className="forecast-score compact"><b>{score.correct}/{score.done}</b><span>richtig</span></div>
        </div>
        <div className="reaction-progress">Reaktion {idx + 1} / {list.length} · {r.teil}</div>
        <div className="reaction-prompt">
          <h3>{r.name}</h3>
          {r.conditions && <p className="muted">Bedingungen: {r.conditions}</p>}
          {r.hint && (showHint
            ? <p className="reaction-hint">💡 {r.hint}</p>
            : <button type="button" className="reaction-hint-btn" onClick={() => setShowHint(true)}>Tipp anzeigen</button>)}
        </div>
        <input
          className="reaction-input"
          placeholder="z. B. N2 + 3 H2 -> 2 NH3"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !result) checkAnswer(); }}
          disabled={!!result && !result.form_error}
          autoFocus
        />
        {!result && (
          <button className="primary" disabled={busy || !answer.trim()} onClick={checkAnswer}>Prüfen</button>
        )}
        {result && result.form_error && (
          <div className="reaction-result form">
            <p>{result.message}</p>
            <button onClick={() => setResult(null)}>Nochmal</button>
          </div>
        )}
        {result && !result.form_error && (
          <div className={`reaction-result ${result.correct ? "ok" : "bad"}`}>
            {result.correct
              ? <p><b>✓ Richtig!</b></p>
              : <>
                  <p><b>✗ Noch nicht ganz.</b></p>
                  {!!result.missing_products?.length && <p>Fehlende Produkte: {result.missing_products.join(", ")}</p>}
                  {!!result.extra_products?.length && <p>Zu viel bei den Produkten: {result.extra_products.join(", ")}</p>}
                  {!!result.missing_educts?.length && <p>Fehlende Edukte: {result.missing_educts.join(", ")}</p>}
                  {!!result.extra_educts?.length && <p>Zu viel bei den Edukten: {result.extra_educts.join(", ")}</p>}
                </>}
            <p className="reaction-reference">Lösung: <b>{result.reference}</b>{result.conditions ? ` (${result.conditions})` : ""}</p>
            <button className="primary" onClick={next}>Nächste Reaktion →</button>
          </div>
        )}
      </div>
    </section>
  );
}

function AntwortCheckPage({ module, sessionSize = 20, setSessionSize }) {
  const [cards, setCards] = useState([]);
  const [idx, setIdx] = useState(0);
  const [answer, setAnswer] = useState("");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [coach, setCoach] = useState(null);
  const [error, setError] = useState(false);

  async function loadCards() {
    setError(false);
    try {
      const res = await api(`/api/study/anki?module=${module}&limit=${sessionSize}`);
      setCards(res.cards || []);
      setIdx(0); setAnswer(""); setResult(null);
    } catch (err) { setError(true); }
  }
  useEffect(() => { loadCards(); }, [module, sessionSize]);
  useEffect(() => { api("/api/coach/status").then(setCoach).catch(() => {}); }, []);

  const card = cards[idx];
  const question = card ? (card.q.split("\n\n").pop() || card.q) : "";

  async function grade() {
    if (!card || !answer.trim()) return;
    setBusy(true); setResult(null);
    try {
      const res = await api("/api/coach/grade", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ card_id: card.id, answer }),
      });
      setResult(res);
    } catch (err) {
      setResult({ error: err.message });
    } finally { setBusy(false); }
  }
  function next() {
    setAnswer(""); setResult(null);
    if (idx + 1 >= cards.length) loadCards().catch(() => {});
    else setIdx(idx + 1);
  }

  if (!card) return error
    ? <LoadError onRetry={loadCards} label="Antwort-Check konnte nicht geladen werden." />
    : <div className="loading">Antwort-Check laedt...</div>;
  const label = result?.score_label;
  const badge = { full: ["Voll", "var(--ok)"], partial: ["Teilweise", "var(--warn-strong)"], miss: ["Verfehlt", "var(--bad)"] }[label] || ["", "var(--muted)"];
  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><Sparkles size={18} /> Antwort-Check</h2>
          <p>Frei formulieren wie in der Pruefung – dann bewerten lassen.</p></div>
        <label className="session-size light" title="Karten pro Runde">
          <span className="muted" style={{ marginRight: 6 }}>Karten/Runde</span>
          <select value={sessionSize} onChange={(e) => setSessionSize?.(Number(e.target.value))}>
            {[10, 15, 20, 25, 30, 40, 50].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        </label>
      </div>
      {coach && !coach.available && (
        <div className="form-msg">Kein KI-Key aktiv – Bewertung erfolgt über Stichwort-Näherung. (ANTHROPIC_API_KEY setzen für echtes KI-Feedback.)</div>
      )}
      <div style={{ padding: 12, background: "var(--surface-2,#f4f6f8)", borderRadius: 8, marginBottom: 10 }}>
        <small className="muted">VO{card.kap}</small>
        <p style={{ margin: "4px 0 0", fontWeight: 600 }}>{question}</p>
      </div>
      <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} rows={6}
        placeholder="Deine Antwort..." style={{ width: "100%", padding: 10, borderRadius: 6, fontFamily: "inherit" }} />
      <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
        <button className="primary" onClick={grade} disabled={busy || !answer.trim()}>{busy ? "Bewerte..." : "Bewerten"}</button>
        <button onClick={next}>Nächste Frage</button>
      </div>
      {result && !result.error && (
        <div style={{ marginTop: 14 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ padding: "4px 12px", borderRadius: 16, color: "#fff", background: badge[1], fontWeight: 600 }}>
              {badge[0]} · {result.score_pct}%
            </span>
            {result.offline && <small className="muted">(Stichwort-Näherung)</small>}
            {typeof result.xp?.total_xp === "number" && <small className="muted">+XP</small>}
          </div>
          <p style={{ margin: "10px 0" }}>{result.feedback}</p>
          {(result.missed_points || []).length > 0 && (
            <div style={{ marginBottom: 8 }}>
              <b style={{ color: "var(--bad)" }}>Noch offen:</b>
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {result.missed_points.map((p, i) => <li key={i}>{p}</li>)}
              </ul>
            </div>
          )}
          <details>
            <summary style={{ cursor: "pointer" }}>Musterlösung anzeigen</summary>
            <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
              {(result.model_points || []).map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          </details>
        </div>
      )}
      {result?.error && <div className="form-msg">Fehler: {result.error}</div>}
    </section>
  );
}

const LU_STATUS = {
  neu: ["#8a94a6", "neu"], gelernt: ["#30a46c", "gelernt"],
  faellig: ["#e0a015", "faellig"], inaktiv: ["#8a94a6", "inaktiv"], fehlt: ["#8a94a6", "-"],
};

function LernunterlagenPage({ module, setModule, modules }) {
  const [index, setIndex] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [page, setPage] = useState(1);
  const [openPage, setOpenPage] = useState(null);
  const [error, setError] = useState(false);

  useEffect(() => { api("/api/lernunterlagen").then(setIndex).catch(() => setError(true)); }, []);

  const chapters = (index?.chapters || []).filter((c) => c.module === module);

  function open(ch) {
    setLoadingDetail(true); setDetail(null); setPage(1); setOpenPage(null);
    api(`/api/lernunterlagen/${ch.module}/${ch.kap}`)
      .then((d) => { setDetail(d); setLoadingDetail(false); })
      .catch(() => { setError(true); setLoadingDetail(false); });
  }

  // Beim Modulwechsel / Erst-Laden das erste Kapitel oeffnen.
  useEffect(() => {
    if (chapters.length && (!detail || detail.module !== module)) open(chapters[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [module, index]);

  if (error) return <LoadError onRetry={() => window.location.reload()} label="Lernunterlagen konnten nicht geladen werden." />;
  if (!index) return <div className="loading">Lernunterlagen laden...</div>;

  const curKap = detail?.kap;
  const coveredPages = detail ? Object.keys(detail.page_cards).map(Number).sort((a, b) => a - b) : [];
  const pdfSrc = detail ? `/lernunterlagen/${encodeURIComponent(detail.file)}#page=${page}&view=FitH` : null;

  return (
    <section className="panel lu">
      <div className="section-head">
        <div><h2><FileText size={18} /> Lernunterlagen</h2>
          <p>Original-Foliensaetze mit markierten Seiten und den zugehoerigen Fragen.</p></div>
        {setModule && (
          <div className="module-switch">
            <button className={module === "organic" ? "active" : ""} onClick={() => setModule("organic")}>Organik</button>
            <button className={module === "inorganic" ? "active" : ""} onClick={() => setModule("inorganic")}>Anorganik</button>
          </div>
        )}
      </div>
      <div className="lu-grid">
        <aside className="lu-chapters">
          {chapters.map((ch) => {
            const pct = ch.cards_total ? Math.round(100 * ch.cards_anchored / ch.cards_total) : 0;
            const label = module === "organic" ? `VO${ch.kap}` : `Einheit ${String(ch.kap).padStart(2, "0")}`;
            const title = ch.title.replace(/^VO\d+\s*/, "").replace(/^Einheit \d+\s*/, "");
            return (
              <button key={ch.kap} className={`lu-chap ${curKap === ch.kap ? "active" : ""}`} onClick={() => open(ch)}>
                <b>{label}</b>
                <span className="lu-chap-title">{title}</span>
                <em>{ch.cards_total} Fragen &middot; {ch.pages} S.{ch.available ? "" : " · PDF fehlt"}</em>
                <i className="lu-bar"><span style={{ width: `${pct}%` }} /></i>
              </button>
            );
          })}
        </aside>

        <div className="lu-pdf">
          {loadingDetail && <div className="loading">Kapitel laedt...</div>}
          {detail && !detail.available && (
            <div className="form-msg">Dieses PDF liegt noch nicht auf dem Server. Die Seiten- und Fragen-Uebersicht rechts funktioniert trotzdem.</div>
          )}
          {detail && detail.available && pdfSrc && (
            <>
              <div className="lu-pdf-bar">
                <span className="lu-pdf-title">{detail.title} &middot; Seite {page}/{detail.pages}</span>
                <a className="lu-open" href={pdfSrc} target="_blank" rel="noreferrer">
                  In neuem Tab oeffnen <ArrowLeft size={13} style={{ transform: "rotate(135deg)" }} />
                </a>
              </div>
              <iframe key={detail.file} title={detail.title} src={pdfSrc} className="lu-frame" />
            </>
          )}
        </div>

        <aside className="lu-pages">
          {detail && (
            <>
              <div className="lu-cov">
                <b>{detail.cards_anchored}/{detail.cards_total}</b> Fragen verortet &middot; {coveredPages.length} Seiten markiert
              </div>
              {coveredPages.map((pg) => {
                const cards = detail.page_cards[String(pg)];
                const isOpen = openPage === pg;
                return (
                  <div key={pg} className={`lu-page ${page === pg ? "current" : ""}`}>
                    <button className="lu-page-head" onClick={() => { setPage(pg); setOpenPage(isOpen ? null : pg); }}>
                      <span className="lu-pg">S. {pg}</span>
                      <span className="lu-cnt">{cards.length} {cards.length === 1 ? "Frage" : "Fragen"}</span>
                      <ChevronDown size={14} className={`lu-chev ${isOpen ? "open" : ""}`} />
                    </button>
                    {isOpen && (
                      <ul className="lu-qs">
                        {cards.map((c) => (
                          <li key={c.id}>
                            <i className="lu-dot" style={{ background: (LU_STATUS[c.status] || LU_STATUS.neu)[0] }} title={(LU_STATUS[c.status] || [])[1]} />
                            {c.q}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
              {detail.unanchored.length > 0 && (
                <details className="lu-unanchored">
                  <summary>{detail.unanchored.length} weitere Fragen (Seite unklar)</summary>
                  <ul className="lu-qs">
                    {detail.unanchored.map((c) => (
                      <li key={c.id}><i className="lu-dot" style={{ background: (LU_STATUS[c.status] || LU_STATUS.neu)[0] }} />{c.q}</li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

const NAV_GROUPS = [
  {
    label: "Lernen", icon: Target,
    items: [
      { route: "exam", label: "Pruefung", icon: Target },
      { route: "lernunterlagen", label: "Lernunterlagen", icon: FileText },
      { route: "antwortcheck", label: "Antwort-Check", icon: Sparkles },
      { route: "reactions", label: "Reaktionen", icon: FlaskConical },
      { route: "processes", label: "Prozesse", icon: ListOrdered },
      { route: "confusions", label: "Verwechslungen", icon: Split },
      { route: "fehlerbuch", label: "Fehlerbuch", icon: AlertTriangle },
      { route: "lastminute", label: "Spickzettel", icon: ListChecks },
    ],
  },
  {
    label: "Fortschritt", icon: BarChart3,
    items: [
      { route: "studyplan", label: "Lernplan", icon: CalendarDays },
      { route: "dashboard", label: "Dashboard", icon: BarChart3 },
      { route: "analytics", label: "Analytics", icon: Gauge },
      { route: "readiness", label: "Reifeplan", icon: CalendarClock },
      { route: "pomodoro", label: "Pomodoro", icon: Timer },
      { route: "knowledge", label: "Landkarte", icon: Tag },
      { route: "quests", label: "Quests", icon: Trophy },
    ],
  },
  {
    label: "Karten", icon: Edit3,
    items: [
      { route: "quality-center", label: "Qualitaet", icon: ClipboardList },
      { route: "workshop", label: "Werkstatt", icon: Edit3 },
      { route: "triage", label: "Triage", icon: ClipboardList },
      { route: "quality", label: "Kartenqualitaet", icon: ClipboardList },
      { route: "photos", label: "Fotopool", icon: ImagePlus },
      { route: "add", label: "Eigene Karte", icon: Plus },
      { route: "import", label: "Import", icon: ClipboardList },
    ],
  },
];

function NavBar({ route, setRoute }) {
  const [open, setOpen] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(null); };
    const onKey = (e) => { if (e.key === "Escape") setOpen(null); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const go = (r) => { setRoute(r); setOpen(null); };

  return (
    <nav className="tabs" ref={ref}>
      <button className={route === "home" ? "active" : ""} onClick={() => go("home")}>
        <BookOpenCheck size={16} /> Trainer
      </button>
      {NAV_GROUPS.map((group) => {
        const GroupIcon = group.icon;
        const activeInGroup = group.items.some((it) => it.route === route);
        const isOpen = open === group.label;
        return (
          <div className="nav-group" key={group.label}>
            <button
              className={`nav-group-btn${activeInGroup ? " active" : ""}${isOpen ? " open" : ""}`}
              onClick={() => setOpen(isOpen ? null : group.label)}
              aria-expanded={isOpen}
              aria-haspopup="true"
            >
              <GroupIcon size={16} /> {group.label}
              <ChevronDown size={14} className="nav-chevron" />
            </button>
            {isOpen && (
              <div className="nav-dropdown" role="menu">
                {group.items.map((it) => {
                  const ItemIcon = it.icon;
                  return (
                    <button
                      key={it.route}
                      role="menuitem"
                      className={route === it.route ? "active" : ""}
                      onClick={() => go(it.route)}
                    >
                      <ItemIcon size={16} /> {it.label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}

function LoadError({ onRetry, label = "Konnte nicht geladen werden." }) {
  return (
    <div className="loading load-error">
      <p>{label}</p>
      <p className="muted">Pruefe die Verbindung und versuche es erneut.</p>
      <button className="primary" onClick={onRetry}>Erneut versuchen</button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Pomodoro-Verknüpfung: steuert den externen Pomodoro-Timer
// (pomodoro.stoegerer-home.cloud) per Maschinen-Token. Aktives Lernen ->
// Fokus-Timer fürs aktuelle Modul; Inaktivität/Tab-Wechsel -> Pause.
// Konfiguration liegt lokal im Browser (localStorage), Token bleibt clientseitig.
// ---------------------------------------------------------------------------
const POMO_DEFAULT_URL = "https://pomodoro.stoegerer-home.cloud";
const pomoCfg = () => ({
  enabled: localStorage.getItem("pomo_enabled") === "1",
  url: (localStorage.getItem("pomo_url") || POMO_DEFAULT_URL).replace(/\/+$/, ""),
  token: localStorage.getItem("pomo_token") || "",
  cat: {
    organic: localStorage.getItem("pomo_cat_organic") || "",
    inorganic: localStorage.getItem("pomo_cat_inorganic") || "",
  },
  idle: Math.max(5, parseInt(localStorage.getItem("pomo_idle") || "25", 10) || 25),
});

function pomoFocus(cfg, category, action) {
  // action: "start" | "pause"; Fehler werden geschluckt (-> false). Harter Timeout via
  // AbortController, damit fetch IMMER terminiert - sonst koennte ein haengender Request
  // den inFlight-Guard dauerhaft blockieren und die Synchronisation ausfallen lassen.
  const u = `${cfg.url}/api/study-time/${encodeURIComponent(category)}/focus/${action}?token=${encodeURIComponent(cfg.token)}`;
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 8000);
  return fetch(u, { method: "POST", keepalive: true, signal: ctrl.signal })
    .then((r) => r.ok).catch(() => false).finally(() => clearTimeout(t));
}

function usePomodoroSync(module) {
  const [status, setStatus] = useState({ enabled: false, running: false, category: null, error: null });
  const lastActivity = useRef(Date.now());
  const lastSent = useRef({ run: null, cat: null });
  const inFlight = useRef(false); // verhindert ueberlappende Aufrufe bei langsamen Requests
  const moduleRef = useRef(module);
  moduleRef.current = module;

  // Aktivität erfassen.
  useEffect(() => {
    const bump = () => { lastActivity.current = Date.now(); };
    const evs = ["mousemove", "mousedown", "keydown", "scroll", "touchstart", "wheel"];
    evs.forEach((e) => window.addEventListener(e, bump, { passive: true }));
    return () => evs.forEach((e) => window.removeEventListener(e, bump));
  }, []);

  // Sofort pausieren, wenn der Tab in den Hintergrund geht (Timer sind dann gedrosselt).
  useEffect(() => {
    const onHide = () => {
      if (document.visibilityState !== "hidden") return;
      const cfg = pomoCfg();
      if (!cfg.enabled || !cfg.token) return;
      const cat = cfg.cat[moduleRef.current];
      if (cat && lastSent.current.run === true) {
        // Best-effort-Sofortpause; lastSent NICHT umstellen -> schlaegt die Pause fehl,
        // holt der periodische Abgleich sie beim naechsten sichtbaren Tick nach.
        pomoFocus(cfg, cat, "pause");
      }
    };
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, []);

  // Regelmäßiger Abgleich.
  useEffect(() => {
    let stopped = false;
    // Status nur setzen, wenn sich wirklich etwas geaendert hat - sonst wuerde das
    // 4s-Intervall auch bei DEAKTIVIERTER Integration jedes Mal ein neues Objekt setzen
    // und App 15x/min unnoetig neu rendern.
    const apply = (next) => setStatus((s) =>
      (s.enabled === next.enabled && s.running === next.running &&
       s.category === next.category && s.error === next.error) ? s : next);
    async function tick() {
      if (stopped || inFlight.current) return;   // keine ueberlappenden Aufrufe
      const cfg = pomoCfg();
      if (!cfg.enabled || !cfg.url || !cfg.token) {
        // Beim Deaktivieren einen noch laufenden Fokus sauber pausieren, bevor wir den
        // Zustand vergessen - sonst liefe der externe Timer unbemerkt weiter. lastSent
        // erst nach ERFOLGREICHER Pause vergessen, sonst geht der Retry verloren.
        if (lastSent.current.run === true && lastSent.current.cat && cfg.url && cfg.token) {
          inFlight.current = true;
          let ok;
          try { ok = await pomoFocus(cfg, lastSent.current.cat, "pause"); }
          finally { inFlight.current = false; }
          if (!ok) { apply({ enabled: false, running: false, category: null, error: "Verbindungsfehler" }); return; }
        }
        lastSent.current = { run: null, cat: null };
        apply({ enabled: false, running: false, category: null, error: null });
        return;
      }
      const cat = cfg.cat[module];
      if (!cat) {
        // Kein Ziel fuers aktuelle Modul: einen evtl. noch laufenden Fokus (z.B. aus dem
        // vorherigen Modul, dessen Cleanup-Pause fehlschlug) ZUVERLAESSIG pausieren -
        // sonst liefe der externe Timer dauerhaft weiter. Mit Retry, da wir lastSent nur
        // bei Erfolg umstellen.
        if (lastSent.current.run === true && lastSent.current.cat) {
          inFlight.current = true;
          let ok;
          try { ok = await pomoFocus(cfg, lastSent.current.cat, "pause"); }
          finally { inFlight.current = false; }
          if (ok) lastSent.current = { run: false, cat: lastSent.current.cat };
        }
        apply({ enabled: true, running: false, category: null, error: "Kategorie für dieses Modul nicht gesetzt" });
        return;
      }
      // Aktiv = kürzlich Aktivität. Ein versteckter Tab bekommt keine Maus-/
      // Tastenaktivität -> pausiert nach Ablauf ohnehin; zusätzlich pausiert der
      // visibilitychange-Handler sofort beim Wegwechseln.
      const active = (Date.now() - lastActivity.current) < cfg.idle * 1000;
      if (active) {
        if (lastSent.current.run !== true || lastSent.current.cat !== cat) {
          inFlight.current = true;
          let ok;
          try { ok = await pomoFocus(cfg, cat, "start"); }
          finally { inFlight.current = false; }
          // lastSent NUR bei Erfolg umstellen -> ein fehlgeschlagener Start wird beim
          // naechsten Tick erneut versucht (statt faelschlich als "laeuft" zu gelten).
          if (ok) lastSent.current = { run: true, cat };
          apply({ enabled: true, running: ok, category: cat, error: ok ? null : "Verbindungsfehler" });
        } else {
          apply({ enabled: true, running: true, category: cat, error: null });
        }
      } else if (lastSent.current.run !== false) {
        inFlight.current = true;
        let ok;
        try { ok = await pomoFocus(cfg, cat, "pause"); }
        finally { inFlight.current = false; }
        // Nur bei erfolgreicher Pause als pausiert merken - sonst Retry beim naechsten
        // Tick, damit ein extern weiterlaufender Timer nicht unbemerkt bleibt.
        if (ok) lastSent.current = { run: false, cat };
        apply({ enabled: true, running: !ok, category: cat, error: ok ? null : "Verbindungsfehler" });
      } else {
        apply({ enabled: true, running: false, category: cat, error: null });
      }
    }
    tick();
    const id = setInterval(tick, 4000);
    return () => {
      stopped = true;
      clearInterval(id);
      // Modulwechsel/Unmount: den laufenden Fokus des BISHERIGEN Moduls best-effort
      // pausieren. lastSent wird NICHT umgestellt (das Ergebnis kann im synchronen
      // Cleanup nicht abgewartet werden) -> der neu montierte Effekt gleicht anhand des
      // echten lastSent ab: schlaegt die Pause fehl, holt der naechste Tick sie nach;
      // bei Modulwechsel schaltet der Start des neuen Moduls den (einen) Server-Timer um.
      const cfg = pomoCfg();
      if (cfg.enabled && cfg.url && cfg.token && lastSent.current.run === true && lastSent.current.cat) {
        pomoFocus(cfg, lastSent.current.cat, "pause");
      }
    };
  }, [module]);

  return status;
}

function PomodoroChip({ status, setRoute }) {
  if (!status.enabled) return null;
  const color = status.error ? "var(--bad)" : status.running ? "var(--ok)" : "var(--muted)";
  const label = status.error ? "Fehler" : status.running ? `läuft · ${status.category}` : "pausiert";
  return (
    <button className="pomo-chip" title="Pomodoro-Verknüpfung" onClick={() => setRoute?.("pomodoro")}>
      🍅 <span className="pomo-dot" style={{ background: color }} /> {label}
    </button>
  );
}

function PomodoroSettings({ module }) {
  const [url, setUrl] = useState(localStorage.getItem("pomo_url") || POMO_DEFAULT_URL);
  const [token, setToken] = useState(localStorage.getItem("pomo_token") || "");
  const [enabled, setEnabled] = useState(localStorage.getItem("pomo_enabled") === "1");
  const [idle, setIdle] = useState(localStorage.getItem("pomo_idle") || "25");
  const [catO, setCatO] = useState(localStorage.getItem("pomo_cat_organic") || "");
  const [catA, setCatA] = useState(localStorage.getItem("pomo_cat_inorganic") || "");
  const [cats, setCats] = useState(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  function save() {
    localStorage.setItem("pomo_url", url.replace(/\/+$/, ""));
    localStorage.setItem("pomo_token", token.trim());
    localStorage.setItem("pomo_enabled", enabled ? "1" : "0");
    localStorage.setItem("pomo_idle", String(Math.max(5, parseInt(idle, 10) || 25)));
    localStorage.setItem("pomo_cat_organic", catO);
    localStorage.setItem("pomo_cat_inorganic", catA);
    setMsg("Gespeichert.");
  }
  async function connect() {
    setBusy(true); setMsg("");
    try {
      const base = url.replace(/\/+$/, "");
      const r = await fetch(`${base}/api/study-time?token=${encodeURIComponent(token.trim())}`);
      if (!r.ok) throw new Error(r.status === 401 ? "Token ungültig" : `HTTP ${r.status}`);
      const list = await r.json();
      const names = (Array.isArray(list) ? list : []).map((c) => c.category).filter(Boolean);
      setCats(names);
      // Sinnvolle Vorauswahl per Namensheuristik.
      if (!catO) { const g = names.find((n) => /organ/i.test(n) && !/anorgan/i.test(n)); if (g) setCatO(g); }
      if (!catA) { const g = names.find((n) => /anorgan/i.test(n)); if (g) setCatA(g); }
      setMsg(`Verbunden – ${names.length} Projekte gefunden.`);
    } catch (e) {
      setCats(null); setMsg("Verbindung fehlgeschlagen: " + (e.message || e));
    } finally { setBusy(false); }
  }
  const catInput = (val, set, label) => (
    <label className="pomo-field">
      <span>{label}</span>
      {cats
        ? <select value={val} onChange={(e) => set(e.target.value)}>
            <option value="">– Projekt wählen –</option>
            {cats.map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
        : <input value={val} onChange={(e) => set(e.target.value)} placeholder="Projektname im Pomodoro" />}
    </label>
  );

  return (
    <section className="panel">
      <div className="section-head">
        <div><h2><Timer size={18} /> Pomodoro-Verknüpfung</h2>
          <p>Beim Lernen startet der Fokus-Timer im gewählten Projekt; bei Inaktivität pausiert er.</p></div>
      </div>
      <div className="pomo-form">
        <label className="pomo-field"><span>Pomodoro-URL</span>
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={POMO_DEFAULT_URL} /></label>
        <label className="pomo-field"><span>API-Token <small className="muted">(Pomodoro → Einstellungen → Sicherheit)</small></span>
          <input type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder="API-Token" /></label>
        <div className="pomo-row">
          <button onClick={connect} disabled={busy || !token.trim()}>{busy ? "Verbinde…" : "Verbinden & Projekte laden"}</button>
          {msg && <span className="muted" style={{ fontSize: 13 }}>{msg}</span>}
        </div>
        {catInput(catO, setCatO, "Projekt für Organik")}
        {catInput(catA, setCatA, "Projekt für Anorganik")}
        <label className="pomo-field"><span>Pause nach Inaktivität (Sekunden)</span>
          <input type="number" min="5" value={idle} onChange={(e) => setIdle(e.target.value)} style={{ maxWidth: 120 }} /></label>
        <label className="pomo-toggle">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          <span>Verknüpfung aktiv</span>
        </label>
        <div className="pomo-row">
          <button className="primary" onClick={save}>Speichern</button>
          <span className="muted" style={{ fontSize: 12 }}>Aktuelles Modul: {module === "inorganic" ? "Anorganik" : "Organik"}</span>
        </div>
        <small className="muted">Der Token wird nur lokal in deinem Browser gespeichert und direkt an deinen Pomodoro-Server geschickt.</small>
      </div>
    </section>
  );
}

function App() {
  const isLogin = window.location.pathname === "/login";
  const [route, setRoute] = useState("home");
  const [module, setModule] = useState("organic");
  const [data, setData] = useState(null);
  const [loadError, setLoadError] = useState(false);
  const loadSeq = useRef(0); // Sequenz-Guard gegen verspaetete Stats-Antworten (Modulwechsel)
  const [session, setSession] = useState(null);
  const [lightbox, setLightbox] = useState(null);
  // Konfigurierbare Session-Groesse (Anzahl Karten pro Lernsession), im Browser gespeichert.
  const [sessionSize, setSessionSizeState] = useState(() => {
    const saved = parseInt(localStorage.getItem("sr_session_size") || "", 10);
    return Number.isFinite(saved) && saved > 0 ? saved : 20;
  });
  const setSessionSize = (n) => {
    const v = Math.max(5, Math.min(100, Number(n) || 20));
    setSessionSizeState(v);
    try { localStorage.setItem("sr_session_size", String(v)); } catch (e) { /* Speicher evtl. blockiert */ }
  };
  // Pomodoro-Verknüpfung: startet/pausiert den externen Fokus-Timer je nach Modul & Aktivität.
  const pomoStatus = usePomodoroSync(module);

  async function load() {
    // Sequenz-Guard: nur die Antwort des ZULETZT gestarteten load() zaehlt. Sonst koennte
    // eine verspaetete Antwort fuers alte Modul (nach einem Modulwechsel waehrend des
    // Ladens) die neuen Daten ueberschreiben - inkl. falschem Titel/Pruefungstermin.
    const seq = ++loadSeq.current;
    const reqModule = module;
    setLoadError(false);
    try {
      const res = await api(`/api/stats?module=${encodeURIComponent(reqModule)}`);
      if (seq !== loadSeq.current) return;   // veraltete Antwort verwerfen
      setData(res);
    } catch (err) {
      if (seq !== loadSeq.current) return;
      // Ohne Fehlerzustand bliebe data null und die App haengt dauerhaft bei "Laedt...".
      setLoadError(true);
    }
  }
  useEffect(() => {
    if (isLogin) return;
    // Beim Modulwechsel die alten Daten verwerfen: sonst bleibt bei einem fehlgeschlagenen
    // load() das vorige Modul (Titel, Pruefungstermin) sichtbar, obwohl der andere
    // Schalter aktiv ist. Mit data===null greift dann der LoadError-Zustand.
    setData(null);
    setLoadError(false);
    load();
  }, [isLogin, module]);

  async function startSession(deck = "anki", kap = null, block = null) {
    const qs = new URLSearchParams({ limit: String(sessionSize) });
    if (kap) qs.set("kap", String(kap));
    if (block) qs.set("block", block);  // ganzer Pruefungs-Teil
    qs.set("module", module);
    const res = await api(`/api/study/${deck}?${qs}`);
    setSession({ deck, module, cards: res.cards || [], idx: 0, kap, block });
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

  async function startMockExam() {
    const res = await api(`/api/mock-exam?module=${encodeURIComponent(module)}`);
    setSession({
      deck: "exam",
      module,
      mock: true,
      exam_id: res.exam_id,
      title: res.title || "Volle Prüfung",
      minutes: res.minutes || Math.max(10, Math.round((res.cards || []).length * .9)),
      cards: res.cards || [],
      idx: 0,
      mode: "mixed",
      results: [],
      startedAt: Date.now(),
    });
  }

  async function finishSession() {
    setSession(null);
    await load();
  }

  const content = useMemo(() => {
    if (!data) return loadError
      ? <LoadError onRetry={load} label="Die App konnte nicht geladen werden." />
      : <div className="loading">Laedt...</div>;
    if (session) return <Study session={session} setSession={setSession} finish={finishSession} />;
    if (route === "dashboard") return <Dashboard startSession={startSession} module={module} />;
    if (route === "knowledge") return <KnowledgeMapPage module={module} startSession={startSession} setRoute={setRoute} />;
    if (route === "exam") return <ExamPage startExam={startExam} startMockExam={startMockExam} startSession={startSession} module={module} />;
    if (route === "quality-center") return <QualityCenter data={data} setRoute={setRoute} module={module} startSession={startSession} />;
    if (route === "workshop") return <WorkshopPage module={module} onDone={load} />;
    if (route === "triage") return <TriagePage module={module} onDone={load} />;
    if (route === "quality") return <CardReviewPage onDone={load} module={module} />;
    if (route === "photos") return <PhotoPoolPage onDone={load} startSession={startSession} />;
    if (route === "add") return <ManualCardPage onDone={load} module={module} />;
    if (route === "import") return <CardImportPage onDone={load} module={module} />;
    if (route === "fehlerbuch") return <FehlerbuchPage module={module} startSession={startSession} />;
    if (route === "analytics") return <AnalyticsPage module={module} />;
    if (route === "readiness") return <ReadinessPage module={module} startExam={startExam} setRoute={setRoute} startSession={startSession} />;
    if (route === "pomodoro") return <PomodoroSettings module={module} />;
    if (route === "studyplan") return <StudyPlanPage module={module} startSession={startSession} startExam={startExam} setRoute={setRoute} />;
    if (route === "lernunterlagen") return <LernunterlagenPage module={module} setModule={setModule} modules={data.modules} />;
    if (route === "antwortcheck") return <AntwortCheckPage module={module} sessionSize={sessionSize} setSessionSize={setSessionSize} />;
    if (route === "reactions") return <ReactionTrainerPage module={module} />;
    if (route === "processes") return <ProcessTrainerPage module={module} />;
    if (route === "confusions") return <ConfusionTrainerPage module={module} />;
    if (route === "lastminute") return <LastMinutePage module={module} />;
    if (route === "quests") return <QuestsPage module={module} />;
    return <Home data={data} startSession={startSession} startExam={startExam} setRoute={setRoute} refresh={load} module={module} setModule={setModule} sessionSize={sessionSize} setSessionSize={setSessionSize} />;
  }, [data, loadError, session, route, module, sessionSize]);

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
      <PomodoroChip status={pomoStatus} setRoute={setRoute} />
      <NavBar route={route} setRoute={setRoute} />
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
