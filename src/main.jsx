import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowLeft,
  BarChart3,
  BookOpenCheck,
  Check,
  Flame,
  LogOut,
  RefreshCw,
  Trophy,
} from "lucide-react";
import "./styles.css";

const RATING_LABELS = { 1: "Nochmal", 2: "Schwer", 3: "Gut", 4: "Leicht" };

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
        <div className="brand-mark">CT</div>
        <h1>Chemie SR-Trainer</h1>
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

function Home({ data, startSession, setRoute, refresh }) {
  const st = data.anki || {};
  const goal = data.daily_goal || {};
  const forecast = data.forecast || {};
  return (
    <>
      <section className="hero">
        <div className="days">{data.days_until_exam}</div>
        <div>
          <h1>Chemische Technologien organischer Stoffe</h1>
          <p>Manuels Anki-Style Trainer bis zur Pruefung am 21.09.2026.</p>
          <div className="hero-actions">
            <button className="primary" onClick={() => startSession("anki")}>Session starten</button>
            <button onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
          </div>
        </div>
      </section>

      <XpCard xp={data.xp} streak={data.streak} />

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

      <section className="deck wide">
        <div className="deck-head">
          <div>
            <h2>Anki-Karten</h2>
            <p>620 Karten aus Skripten, Vokabelsammlungen und Beispielpruefungen. Keine MC-Fragen.</p>
          </div>
          <button className="primary" disabled={!((st.due || 0) + (st.new || 0))} onClick={() => startSession("anki")}>
            Lernen
          </button>
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
  const progress = pct(session.idx, Math.max(cards.length, 1));

  useEffect(() => {
    setRevealed(false);
    setPreview({});
    if (card?.id) api(`/api/preview/${encodeURIComponent(card.id)}`).then(setPreview).catch(() => {});
  }, [card?.id]);

  async function rate(rating) {
    await api("/api/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_id: card.id, rating }),
    });
    if (session.idx + 1 >= cards.length) finish();
    else setSession((old) => ({ ...old, idx: old.idx + 1 }));
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
        <h2 dangerouslySetInnerHTML={{ __html: card.q }} />
        {revealed ? (
          <>
            <div className="answer" dangerouslySetInnerHTML={{ __html: card.a }} />
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

function Dashboard({ startSession }) {
  const [data, setData] = useState(null);
  useEffect(() => {
    api("/api/dashboard").then(setData).catch(() => {});
  }, []);
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
    </>
  );
}

function App() {
  const isLogin = window.location.pathname === "/login";
  const [route, setRoute] = useState("home");
  const [data, setData] = useState(null);
  const [session, setSession] = useState(null);

  async function load() {
    setData(await api("/api/stats"));
  }
  useEffect(() => {
    if (!isLogin) load().catch(() => {});
  }, [isLogin]);

  async function startSession(deck = "anki", kap = null) {
    const qs = new URLSearchParams({ limit: "30" });
    if (kap) qs.set("kap", String(kap));
    const res = await api(`/api/study/${deck}?${qs}`);
    setSession({ deck, cards: res.cards || [], idx: 0, kap });
  }

  async function finishSession() {
    setSession(null);
    await load();
  }

  const content = useMemo(() => {
    if (!data) return <div className="loading">Laedt...</div>;
    if (session) return <Study session={session} setSession={setSession} finish={finishSession} />;
    if (route === "dashboard") return <Dashboard startSession={startSession} />;
    return <Home data={data} startSession={startSession} setRoute={setRoute} refresh={load} />;
  }, [data, session, route]);

  if (isLogin) return <Login />;
  return (
    <main className="wrap">
      <AuthBar />
      <nav className="tabs">
        <button className={route === "home" ? "active" : ""} onClick={() => setRoute("home")}><BookOpenCheck size={16} /> Trainer</button>
        <button className={route === "dashboard" ? "active" : ""} onClick={() => setRoute("dashboard")}><BarChart3 size={16} /> Dashboard</button>
      </nav>
      {content}
    </main>
  );
}

createRoot(document.getElementById("root")).render(<App />);
