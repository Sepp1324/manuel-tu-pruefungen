"""Upgrade-Migrations-Test.

Die Deploy-Smoke laeuft sonst nur gegen eine FRISCHE DB - Upgrade-Migrationen mit bereits
vorhandenen manuellen Aenderungen werden dabei nie geprueft. Dieser Test simuliert genau
das: Erststart (seedet) -> manuelle Textaenderung + eingefuegtes Foto -> erneuter
migrate()+seed() (wie bei einem Deploy) -> beides muss erhalten bleiben.

Laeuft im gebauten Image:  python tests/test_upgrade_migration.py
"""
import os
import sys
import json
import tempfile
import datetime

# /app (mit db.py) auf den Importpfad, egal von wo aufgerufen.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["SR_DB_PATH"] = tempfile.mktemp(suffix=".db")

import db  # noqa: E402


def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    # 1) Erststart: legt Schema an, migriert, seedet.
    db.init_db()
    conn = db.get_conn()
    rows = conn.execute("SELECT id FROM cards WHERE deck='anki' LIMIT 2").fetchall()
    assert len(rows) >= 2, "Seed hat zu wenige Karten angelegt"
    edit_id, photo_id = rows[0]["id"], rows[1]["id"]

    # 2) Echte manuelle Textaenderung ueber den Werkstatt-Pfad -> user_edited=1.
    a0 = json.loads(conn.execute("SELECT payload FROM cards WHERE id=?", (edit_id,)).fetchone()["payload"]).get("a", "")
    db.update_card(conn, edit_id, "MANUELL-GEAENDERT-XYZ", a0, "active", "", _now())

    # 3) Karte mit eingefuegtem Foto simulieren (user_edited=0, Foto im Payload-Text).
    conn.execute(
        "UPDATE cards SET payload=?, user_edited=0, updated_at=? WHERE id=?",
        (json.dumps({"q": 'Frage <img src="/uploads/cards/foo.jpg">', "a": "A"}), _now(), photo_id),
    )
    conn.commit()
    conn.close()

    # 4) "Upgrade"-Deploy simulieren: migrate() + seed() erneut.
    conn = db.get_conn()
    db.migrate(conn)
    db.seed(conn)
    conn.commit()
    q_edit = json.loads(conn.execute("SELECT payload FROM cards WHERE id=?", (edit_id,)).fetchone()["payload"])["q"]
    p_photo = conn.execute("SELECT payload FROM cards WHERE id=?", (photo_id,)).fetchone()["payload"]
    conn.close()

    assert q_edit == "MANUELL-GEAENDERT-XYZ", f"FEHLER: manuelle Textaenderung wurde ueberschrieben: {q_edit!r}"
    assert "/uploads/cards/foo.jpg" in p_photo, "FEHLER: Foto der Karte wurde entfernt"
    print("OK: Upgrade-Migration erhaelt manuelle Textaenderungen und Fotos.")


if __name__ == "__main__":
    main()
