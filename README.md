# TU Chemie SR-Trainer

Eigenstaendige Spaced-Repetition-Website fuer Manuels Chemie-Pruefungen:
Organische Chemie am **21.09.2026**, Anorganische Chemie am **29.09.2026**.

Die App basiert technisch auf der Psychologie-SR-Website, ist aber davon
getrennt:

- eigener SQLite-Datenbestand (`organicsr.db`)
- eigener Cookie (`organicsr_session`)
- eigener k3s-Namespace (`organicsr`)
- eigener Benutzer-Bootstrap (`manuel`)
- keine Multiple-Choice-, Englisch- oder Methodik-Modi
- Modulumschalter fuer Organische und Anorganische Chemie
- 341 pruefungsnahe Anki-Style Karten fuer Organische Chemie
- 419 pruefungsnahe Anki-Style Karten fuer Anorganische Chemie
- offener Pruefungsarbeitsplatz mit 2h-Simulation, Antwortgeruesten,
  Schwaechen-Mini-Pruefung, Reaktions-/Strukturtrainer, Score-Prognose und
  Alte-Pruefungen-Ansicht

## Lokal starten

```bash
cd organicsr
npm install
npm run build
cd app
SR_DB_PATH=../data/organicsr.db ADMIN_USER=manuel ADMIN_PASSWORD=change-me AUTH_COOKIE_SECURE=0 uvicorn main:app --reload
```

Dann im Browser `http://127.0.0.1:8000` oeffnen und mit `manuel` einloggen.

Alternativ (inkl. PostgreSQL + Redis):

```bash
cd organicsr
docker compose up --build
```

## Datenbank: SQLite oder PostgreSQL + Redis

Standard ist SQLite. Fuer PostgreSQL + Redis einfach die Env-Variablen setzen –
derselbe Code laeuft dann auf Postgres, ohne die Variablen bleibt es bei SQLite:

- `DATABASE_URL=postgresql://user:pass@host:5432/dbname` – aktiviert PostgreSQL
  (eine kleine Kompatibilitaetsschicht in `app/postgres_compat.py` uebersetzt die
  sqlite3-Aufrufe). Ist die Variable leer, wird `SR_DB_PATH` (SQLite) genutzt.
- `REDIS_URL=redis://host:6379/0` – aktiviert den Redis-Antwort-Cache fuer teure
  Endpunkte (Stats/Dashboard). Ohne Redis faellt der Cache still auf In-Memory
  zurueck; die App funktioniert immer, auch wenn Redis kurz ausfaellt.
- `RESPONSE_CACHE_TTL` (Default 10 s) steuert die Cache-Lebensdauer.

Der aktive Backend-Status ist unter `GET /api/runtime/storage` sichtbar.

## Karten neu generieren

Die Quellen liegen im Workspace unter `sources/organic_chem`. Die Generatoren
erstellen offene Pruefungsfragen im Stil der Beispielpruefungen:
Erklaeren/Beschreiben/Nennen mit erwarteten Antwortpunkten statt
Lueckentext-Fragmenten. Neue Seeds werden so erzeugt:

```bash
python3 organicsr/tools/generate_organic_cards.py
```

Anorganische Chemie wird aus den PDF-Einheiten im ZIP erzeugt. Das ZIP zuerst in
einen temporaren Ordner mit sauberen Dateinamen extrahieren und dann:

```bash
INORG_SOURCE_DIR=/private/tmp/anorganik_sources_clean python3 tools/generate_inorganic_cards.py
```

Das schreibt:

- `app/seed_data.json` - Karten und Kapitel-Metadaten
- `app/source_text_index.json` - kurzer Extraktionsindex zur Kontrolle

Nach einer Neugenerierung sollten die Karten mit Kontextzeilen angereichert
und Quellen-/Personen-/Firmenrauschen entfernt werden:

```bash
PYTHONPATH=tools:app python3 tools/prune_irrelevant_cards.py
PYTHONPATH=app python3 tools/contextualize_seed_cards.py
```

## Deployment

Die k3s-Manifeste liegen in `k8s/`. Der GitHub-Actions-Workflow
(`.github/workflows/deploy-k3s.yml`) baut das Image, prueft es per Smoke-Test,
wendet die Infrastruktur-Manifeste einzeln an und rollt das Deployment per
`kubectl set image` + `rollout restart` aus – **kein** `apply -k`. Vor dem ersten
Deploy anpassen:

- `k8s/10-storage-local.yaml`: lokalen Storage-Pfad pruefen
- `k8s/30-ingress.yaml`: Hostname setzen
- `k8s/kustomization.yaml`: Image-Tag – nur fuer manuelles `apply -k`; der Workflow
  setzt den Tag selbst

**Admin-Zugang / Secrets:** `k8s/15-secret.yaml` ist nur eine Vorlage und wird vom
Workflow **nicht** angewendet (Platzhalter-Passwort). Stattdessen in GitHub →
Settings → Secrets and variables → Actions hinterlegen:

- `ADMIN_PASSWORD` (**erforderlich**) – starkes Admin-Passwort
- optional `ADMIN_USER` (Default `manuel`), `NOTIFY_TOKEN`, `ANTHROPIC_API_KEY`
- optional `POMODORO_TOKEN` – siehe „Pomodoro-Kopplung" unten

Der Deploy legt `organicsr-secrets` einmalig daraus an, **migriert** ein noch
gesetztes Platzhalter-Passwort auf `ADMIN_PASSWORD` (auch der gespeicherte
Benutzer-Hash wird beim Start umgestellt) und aktiviert optionale Keys nachtraeglich.

SQLite bleibt bei `replicas: 1` und `strategy: Recreate`, damit nie zwei Pods
gleichzeitig in dieselbe DB schreiben.

## Pomodoro-Kopplung (Fokus-Timer startet automatisch)

Sobald Karten gelernt werden (`POST /api/review` bzw. offene Pruefung), pingt
der Trainer die [Pomodoro-App](https://pomodoro.stoegerer-home.cloud) per
Heartbeat. Dort startet dann der Fokus-Timer fuer das passende Projekt —
**„Organische Chemie"** oder **„Anorganische Chemie"** (getrennte Projekte) —
und pausiert ~90 s nach der letzten gelernten Karte automatisch wieder.

Aktivieren: in Pomodoro unter *Einstellungen → Konto → API-Token* Manuels Token
holen und als GitHub-Actions-Secret **`POMODORO_TOKEN`** hinterlegen (oder direkt
im `organicsr-secrets` als Key `pomodoro-token`). Ohne Token ist die Kopplung
einfach aus. Die Ziel-URL steht im Deployment als `POMODORO_URL` (Default
`https://pomodoro.stoegerer-home.cloud`). Die Aufrufe sind fire-and-forget: sie
verzoegern oder brechen einen Review nie.
