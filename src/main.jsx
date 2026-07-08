import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  BarChart3,
  BookOpenCheck,
  Check,
  ClipboardList,
  Edit3,
  Flame,
  LogOut,
  Plus,
  RefreshCw,
  Search,
  Tag,
  Target,
  Trophy,
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
const ALL_REASONS = [...TRIAGE_REASONS, ...REVIEW_REASONS, ...EXAM_REASONS];
const EXAM_EVALS = [
  ["full", "voll"],
  ["partial", "teilweise"],
  ["miss", "nicht gewusst"],
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

function pct(n, d) {
  return d ? Math.round((n / d) * 100) : 0;
}

function formatDate(s) {
  if (!s) return "neu";
  const d = new Date(s);
  return `${d.toLocaleDateString("de-AT")} ${d.toLocaleTimeString("de-AT", { hour: "2-digit", minute: "2-digit" })}`;
}

function reasonLabel(reason) {
  return ALL_REASONS.find(([key]) => key === reason)?.[1] || reason || "Ohne Grund";
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
        <span><b>{plan.new_cards_today}</b> neue Karten</span>
        <span><b>{plan.reviews_today}</b> Wiederholungen</span>
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
          </div>
        </div>
      </section>

      <XpCard xp={data.xp} streak={data.streak} />
      <StudyPlan plan={data.study_plan} startSession={startSession} />

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
  const progress = pct(session.idx, Math.max(cards.length, 1));
  const isExam = session.deck === "exam";

  useEffect(() => {
    setRevealed(false);
    setPreview({});
    setFeedbackReason("");
    if (card?.id) api(`/api/preview/${encodeURIComponent(card.id)}`).then(setPreview).catch(() => {});
  }, [card?.id]);

  async function rate(rating) {
    await api("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        card_id: card.id,
        rating,
        source: isExam ? "exam" : "review",
        feedback_reason: rating === 1 ? feedbackReason : "",
      }),
    });
    const nextResult = { card_id: card.id, rating, kap: card.kap, subname: card.subname };
    if (session.idx + 1 >= cards.length) {
      if (isExam) setSession((old) => ({ ...old, done: true, results: [...(old.results || []), nextResult] }));
      else finish();
    } else {
      setSession((old) => ({ ...old, idx: old.idx + 1, results: [...(old.results || []), nextResult] }));
    }
  }

  if (session.done) {
    const results = session.results || [];
    const strong = results.filter((r) => r.rating >= 3).length;
    const byKap = results.reduce((acc, r) => {
      const key = `VO${r.kap}`;
      acc[key] = acc[key] || { total: 0, ok: 0 };
      acc[key].total += 1;
      if (r.rating >= 3) acc[key].ok += 1;
      return acc;
    }, {});
    return (
      <section className="done exam-result">
        <Check size={32} />
        <h2>Pruefungsmodus abgeschlossen</h2>
        <p>{strong} von {results.length} Karten sicher erinnert.</p>
        <div className="result-grid">
          {Object.entries(byKap).map(([kap, v]) => (
            <span key={kap}><b>{kap}</b>{v.ok}/{v.total}</span>
          ))}
        </div>
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
      </div>
      <article className="study-card">
        <div className="study-meta">
          <span className="deck-pill">VO{card.kap}</span>
          <span>{card.subname}</span>
          <span>Quelle: {card.source}</span>
          <span>faellig: {formatDate(card.due)}</span>
        </div>
        <QuestionContent html={card.q} />
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
          <p>Getrennt nach Zeichnen/Skizzieren und Erklaeren.</p>
        </div>
        <button onClick={onStart}>Trainer starten</button>
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
  const [scores, setScores] = useState({});
  const [confidence, setConfidence] = useState({});
  const [errorTypes, setErrorTypes] = useState({});
  const [startedAt, setStartedAt] = useState(Date.now());
  const [secondsLeft, setSecondsLeft] = useState((exam.minutes || 0) * 60);
  const [result, setResult] = useState(null);
  const question = exam.questions[idx];
  const earned = (exam.questions || []).reduce((sum, q) => sum + scoreForQuestion(scores[q.card_id] || {}, q), 0);

  useEffect(() => {
    setSecondsLeft((exam.minutes || 0) * 60);
    setScores({});
    setConfidence({});
    setErrorTypes({});
    setRevealed({});
    setResult(null);
    setIdx(0);
    setStartedAt(Date.now());
  }, [exam.id]);

  useEffect(() => {
    if (result) return undefined;
    const timer = setInterval(() => setSecondsLeft((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [result]);

  function mark(subId, value) {
    setScores((old) => ({
      ...old,
      [question.card_id]: { ...(old[question.card_id] || {}), [subId]: value },
    }));
  }

  async function finish() {
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
      })),
    };
    const res = await api("/api/exam/open/submit", {
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
        </div>
        <h2 dangerouslySetInnerHTML={{ __html: question.question }} />
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
          <button className="primary" onClick={finish}>Auswerten</button>
        </div>
        {revealed[question.card_id] && (
          <div className="exam-solution">
            <h3>Antwort-Geruest</h3>
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
          <textarea
            rows={7}
            value={answers[currentKey] || ""}
            onChange={(e) => setAnswers((old) => ({ ...old, [currentKey]: e.target.value }))}
            placeholder="Antwort wie in der Pruefung notieren, dann selbst nach Raster bewerten."
          />
        </label>
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
    api(`/api/exam/prognosis?module=${encodeURIComponent(module)}`).then(setPrognosis).catch(() => {});
    api(`/api/exam/archive?module=${encodeURIComponent(module)}`).then(setArchive).catch(() => {});
    api(`/api/exam/mastery?module=${encodeURIComponent(module)}`).then(setMastery).catch(() => {});
    api(`/api/exam/formula-checklist?module=${encodeURIComponent(module)}`).then(setChecklist).catch(() => {});
    api(`/api/exam/final-plan?module=${encodeURIComponent(module)}`).then(setFinalPlan).catch(() => {});
    api(`/api/exam/weekly-plan?module=${encodeURIComponent(module)}`).then(setWeeklyPlan).catch(() => {});
    api(`/api/exam/history?module=${encodeURIComponent(module)}`).then(setHistory).catch(() => {});
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

  async function closeRunner() {
    setExam(null);
    setCorrection(null);
    await loadExamMeta();
  }

  if (correction) return <ArchiveCorrectionRunner exam={correction} module={module} onClose={closeRunner} />;
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
          <button className="primary" onClick={() => startOpen("full")}>2h-Pruefung starten</button>
          <button onClick={() => startOpen("mini")}>Schwaechen-Mini-Pruefung</button>
          <button onClick={() => startOpen("explain")}>Kann ich erklaeren?</button>
          <button onClick={startFormula}>Reaktions-/Strukturtrainer</button>
        </div>
      </div>

      <ExamScorePanel prognosis={prognosis} />
      <AttemptHistoryPanel history={history} />
      <RepairQueuePanel history={history} onStart={() => startSession?.("repair")} />
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
        <label>Frage
          <textarea value={form.q} onChange={(e) => setForm({ ...form, q: e.target.value })} rows={4} />
        </label>
        <label>Antwort
          <textarea value={form.a} onChange={(e) => setForm({ ...form, a: e.target.value })} rows={6} />
        </label>
        <button className="primary"><Plus size={16} /> Speichern</button>
      </form>
      {msg && <div className="form-msg">{msg}</div>}
    </section>
  );
}

function CardReviewPage({ onDone, module }) {
  const [status, setStatus] = useState("needs_review");
  const [kap, setKap] = useState("");
  const [tag, setTag] = useState("");
  const [query, setQuery] = useState("");
  const [data, setData] = useState({ cards: [], summary: {} });
  const [selected, setSelected] = useState(null);
  const [msg, setMsg] = useState("");

  async function load() {
    const qs = new URLSearchParams({ status, limit: "80", module });
    if (kap) qs.set("kap", kap);
    if (tag) qs.set("tag", tag);
    if (query) qs.set("q", query);
    const res = await api(`/api/cards?${qs}`);
    setData(res);
    setSelected(res.cards?.[0] || null);
  }
  useEffect(() => { load().catch(() => {}); }, [status, kap, tag, module]);

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
              <em>{(card.tags || []).join(" · ")}</em>
              <span dangerouslySetInnerHTML={{ __html: card.q }} />
            </button>
          ))}
        </div>
      </div>
      <div className="panel quality-editor">
        {selected ? (
          <>
            <label>Frage
              <textarea value={selected.q || ""} onChange={(e) => setSelected({ ...selected, q: e.target.value })} rows={5} />
            </label>
            <label>Antwort
              <textarea value={selected.a || ""} onChange={(e) => setSelected({ ...selected, a: e.target.value })} rows={9} />
            </label>
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
            <label>Frage
              <textarea value={draft.q || ""} onChange={(e) => setDraft({ ...draft, q: e.target.value })} rows={5} />
            </label>
            <label>Antwort
              <textarea value={draft.a || ""} onChange={(e) => setDraft({ ...draft, a: e.target.value })} rows={9} />
            </label>
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

function QualityCenter({ data, setRoute }) {
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
          <span><b>{autoQuality.moved || 0}</b> auto verschoben</span>
        </div>
        <div className="button-row-inline">
          <button className="primary" onClick={() => setRoute("triage")}><ClipboardList size={16} /> Triage starten</button>
          <button onClick={() => setRoute("quality")}><Search size={16} /> Karten bearbeiten</button>
        </div>
      </div>

      <div className="quality-center-grid">
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

function App() {
  const isLogin = window.location.pathname === "/login";
  const [route, setRoute] = useState("home");
  const [module, setModule] = useState("organic");
  const [data, setData] = useState(null);
  const [session, setSession] = useState(null);

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
    setSession({ deck: "exam", module, cards: res.cards || [], idx: 0, mode, results: [] });
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
    if (route === "quality-center") return <QualityCenter data={data} setRoute={setRoute} />;
    if (route === "triage") return <TriagePage module={module} onDone={load} />;
    if (route === "quality") return <CardReviewPage onDone={load} module={module} />;
    if (route === "add") return <ManualCardPage onDone={load} module={module} />;
    return <Home data={data} startSession={startSession} setRoute={setRoute} refresh={load} module={module} setModule={setModule} />;
  }, [data, session, route, module]);

  if (isLogin) return <Login />;
  return (
    <main className="wrap">
      <AuthBar />
      <nav className="tabs">
        <button className={route === "home" ? "active" : ""} onClick={() => setRoute("home")}><BookOpenCheck size={16} /> Trainer</button>
        <button className={route === "dashboard" ? "active" : ""} onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
        <button className={route === "exam" ? "active" : ""} onClick={() => setRoute("exam")}><Target size={16} /> Pruefung</button>
        <button className={route === "quality-center" ? "active" : ""} onClick={() => setRoute("quality-center")}><ClipboardList size={16} /> Qualitaet</button>
        <button className={route === "triage" ? "active" : ""} onClick={() => setRoute("triage")}><ClipboardList size={16} /> Triage</button>
        <button className={route === "quality" ? "active" : ""} onClick={() => setRoute("quality")}><ClipboardList size={16} /> Kartenqualitaet</button>
        <button className={route === "add" ? "active" : ""} onClick={() => setRoute("add")}><Plus size={16} /> Eigene Karte</button>
      </nav>
      {content}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
