# Organische Chemie SR-Trainer

Eigenstaendige Spaced-Repetition-Website fuer Manuels Pruefung
**Chemische Technologien Organischer Stoffe** am **21.09.2026**.

Die App basiert technisch auf der Psychologie-SR-Website, ist aber davon
getrennt:

- eigener SQLite-Datenbestand (`organicsr.db`)
- eigener Cookie (`organicsr_session`)
- eigener k3s-Namespace (`organicsr`)
- eigener Benutzer-Bootstrap (`manuel`)
- keine Multiple-Choice-, Englisch- oder Methodik-Modi
- 620 Anki-Style Karten aus den hochgeladenen Skripten, Vokabelsammlungen und Beispielpruefungen

## Lokal starten

```bash
cd organicsr
npm install
npm run build
cd app
SR_DB_PATH=../data/organicsr.db ADMIN_USER=manuel ADMIN_PASSWORD=change-me AUTH_COOKIE_SECURE=0 uvicorn main:app --reload
```

Dann im Browser `http://127.0.0.1:8000` oeffnen und mit `manuel` einloggen.

Alternativ:

```bash
cd organicsr
docker compose up --build
```

## Karten neu generieren

Die Quellen liegen im Workspace unter `sources/organic_chem`. Neue Seeds werden
so erzeugt:

```bash
python3 organicsr/tools/generate_organic_cards.py
```

Das schreibt:

- `app/seed_data.json` - Karten und Kapitel-Metadaten
- `app/source_text_index.json` - kurzer Extraktionsindex zur Kontrolle

## Deployment

Die k3s-Manifeste liegen in `k8s/` und sind auf eine separate Instanz
ausgelegt. Vor dem Deploy anpassen:

- `k8s/15-secret.yaml`: starkes `admin-password` setzen
- `k8s/10-storage-nfs.yaml`: NFS-Pfad pruefen
- `k8s/30-ingress.yaml`: Hostname setzen
- `k8s/kustomization.yaml`: Image-Tag setzen

```bash
kubectl apply -k k8s/
```

SQLite bleibt bei `replicas: 1` und `strategy: Recreate`, damit nie zwei Pods
gleichzeitig in dieselbe DB schreiben.
