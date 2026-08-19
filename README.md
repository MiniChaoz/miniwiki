# MiniWiki

Ein schlankes, selbst gehostetes **Wiki / Wissens-Nachschlagewerk** mit Nutzer-Anmeldung
und feiner Zugriffssteuerung. Gedacht für kleine Teams (z. B. IT-Support), die Wissen
zentral, geschützt und durchsuchbar ablegen wollen.

Flask + MySQL (oder SQLite zum Testen), Markdown- **und** WYSIWYG-Editor, Versionsverlauf,
Dateianhänge, Volltext- und Schnellsuche, Hell-/Dunkel-Design.

---

## Inhalt

- [Funktionen](#funktionen)
- [Schnellstart (lokal)](#schnellstart-lokal)
- [Manuelle Installation](#manuelle-installation)
- [Konfiguration](#konfiguration)
- [Produktivbetrieb (Server)](#produktivbetrieb-server)
- [CLI-Befehle](#cli-befehle)
- [Rechte-Modell](#rechte-modell)
- [Sicherheit](#sicherheit)
- [Projektstruktur](#projektstruktur)
- [Aktualisieren](#aktualisieren)
- [Lizenz](#lizenz)

---

## Funktionen

- 🔐 **Anmeldung & Rechte** – von außen ohne Login nichts sichtbar; Zugriff pro Bereich steuerbar
- 🗂️ **Bereiche & Unterbereiche** (Baumstruktur) mit eigenen Seiten
- 🌳 **Seiten mit Unterseiten**, klappbarer Seitenbaum in der Seitenleiste
- ✍️ **Editor mit Umschalter Markdown ⇄ WYSIWYG** (Toast UI), gespeichert wird Markdown
- 🕘 **Versionsverlauf** je Seite inkl. Wiederherstellen
- 🏷️ **Schlagworte (Tags)** + Tag-Übersicht, bereichsübergreifend
- 🔎 **Volltextsuche** (Titel, Inhalt, Tags) + **Schnellsuche `Strg/Cmd + K`**
- 🖼️ **Bild-Uploads** (Einbetten) und 📎 **Datei-Anhänge** (PDF/Logs/… zum Download)
- 📄 **PDF-Export** und Druckansicht je Seite
- 📋 **Seiten-Vorlagen** (z. B. Störungs-Anleitung, Server-Doku) – als neue Seite starten
- ★ **Favoriten** und 🕒 **Zuletzt angesehen**
- 📑 **Automatisches Inhaltsverzeichnis** bei langen Seiten
- 🔀 **Verschieben & Sortieren** (Dialog, Hoch/Runter, Drag & Drop) – rechte-gebunden
- 🌓 **Hell-/Dunkel-Design** (System / Hell / Dunkel), pro Browser gespeichert
- 🕑 **„Letzte Änderungen"** über alle sichtbaren Bereiche

---

## Schnellstart (lokal)

Voraussetzung: **Python 3.11+**. Zum Ausprobieren reicht SQLite – kein MySQL nötig.

**Windows (PowerShell):**
```powershell
.\install.ps1
.\venv\Scripts\python run.py
```

**Linux / macOS:**
```bash
bash install.sh
./venv/bin/python run.py
```

Das Installskript legt eine virtuelle Umgebung an, installiert alles, erstellt eine
`.env` (mit zufälligem `SECRET_KEY`, SQLite) und fragt den ersten Administrator ab.
Danach im Browser: <http://127.0.0.1:5001>

---

## Manuelle Installation

```bash
python -m venv venv
# Windows:        venv\Scripts\activate
# Linux/macOS:    source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # Windows: copy .env.example .env
# In .env einen SECRET_KEY setzen, z. B.:
python -c "import secrets; print(secrets.token_hex(32))"

export FLASK_APP=run.py       # Windows: set FLASK_APP=run.py
flask init-db
flask ensure-schema
flask seed-templates          # optionale Standard-Vorlagen
flask create-admin            # ersten Admin anlegen
python run.py
```

---

## Konfiguration

Alle Einstellungen kommen aus der `.env` (siehe `.env.example`):

| Variable        | Bedeutung                                                        | Beispiel |
|-----------------|------------------------------------------------------------------|----------|
| `SECRET_KEY`    | Signierschlüssel (langer Zufallsstring – **geheim halten!**)     | `token_hex(32)` |
| `DATABASE_URL`  | Datenbank-Verbindung                                             | `mysql+pymysql://wiki:pass@localhost/wiki` oder `sqlite:///wiki.db` |
| `WIKI_NAME`     | Anzeigename im Kopfbereich                                       | `MiniWiki` |
| `INSTANCE_LABEL`| Optionales Banner (z. B. `TEST`), leer = Produktion             | *(leer)* |
| `COOKIE_SECURE` | `true`, wenn hinter HTTPS (empfohlen im Produktivbetrieb)        | `false` |
| `MAX_UPLOAD_MB` | Maximale Upload-Größe in MB                                      | `25` |

---

## Produktivbetrieb (Server)

Empfohlen: **MySQL/MariaDB**, **Gunicorn** und ein Reverse-Proxy (nginx/Caddy) für HTTPS.

1. Datenbank anlegen:
   ```sql
   CREATE DATABASE wiki CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'wiki'@'localhost' IDENTIFIED BY 'DEIN-PASSWORT';
   GRANT ALL PRIVILEGES ON wiki.* TO 'wiki'@'localhost';
   FLUSH PRIVILEGES;
   ```
2. `.env` mit `DATABASE_URL=mysql+pymysql://wiki:DEIN-PASSWORT@localhost/wiki`
   und `COOKIE_SECURE=true`.
3. Schema + Admin: `flask init-db && flask create-admin`
4. Starten:
   ```bash
   gunicorn -w 3 -b 127.0.0.1:5001 run:app
   ```
5. Reverse-Proxy (nginx/Caddy) terminiert HTTPS und leitet auf `127.0.0.1:5001`.
   Beispiel Caddy:
   ```
   wiki.example.com {
       reverse_proxy 127.0.0.1:5001
   }
   ```

### Automatisiertes Deployment (optional)

Für ein frisches Ubuntu/Debian gibt es Helfer-Skripte (nutzen SSH, fragen Zugangsdaten
interaktiv ab – **keine Passwörter in den Dateien**):

- `deploy.py` – richtet alles von Grund auf ein (Pakete, DB, venv, systemd-Service, Firewall)
- `deploy_update.py` – spielt nur Code-Updates ein und startet den Dienst neu

```bash
pip install -r requirements-deploy.txt   # einmalig: benötigt paramiko (SSH)
python deploy.py           # Erstinstallation
python deploy_update.py    # Update
```

---

## CLI-Befehle

```bash
flask init-db          # Tabellen anlegen
flask ensure-schema    # Schema idempotent aktualisieren (neue Tabellen/Spalten)
flask create-admin     # Administrator anlegen / vorhandenen zum Admin machen
flask seed-templates   # nützliche Standard-Vorlagen anlegen
flask seed-demo        # Beispiel-Bereiche + Startseite
```

`seed_content.py` legt zusätzlich ein umfangreiches IT-Nachschlagewerk als Startinhalt an
(idempotent): `python seed_content.py`.

---

## Rechte-Modell

Zugriff = **globale Rolle** (Obergrenze) **plus** **Zugriff pro Bereich**:

| Rolle       | Darf |
|-------------|------|
| **Leser**   | überall höchstens **lesen** |
| **Redakteur** | **lesen & schreiben**, wo der Bereich es erlaubt |
| **Admin**   | **alles** + Nutzer/Bereiche verwalten |

Jeder **Bereich** hat einen **Standardzugriff** (kein / lesen / schreiben) für eingeloggte
Nutzer; zusätzlich sind **Ausnahmen pro Nutzer** je Bereich möglich. Verschieben/Sortieren
von Seiten erfordert Schreibrecht, das von Bereichen ist Admins vorbehalten.

---

## Sicherheit

- Alle Inhalte erfordern Login.
- Seiteninhalte werden serverseitig gerendert und **bereinigt** (Schutz vor XSS).
- **CSRF-Schutz** für alle Formulare.
- Passwörter gehasht (Werkzeug/PBKDF2).
- Bei HTTPS `COOKIE_SECURE=true` setzen.
- **Keine Passwörter/Secrets ins Wiki** – nur Verweise auf einen Passwortmanager.
- `.env`, Datenbank und Uploads liegen außerhalb des Codes und sind per `.gitignore`
  vom Repository ausgeschlossen.

---

## Projektstruktur

```
app/
  __init__.py        App-Factory + CLI-Befehle
  models.py          Datenmodelle (User, Space, Page, Tag, ...)
  permissions.py     Zugriffskontrolle
  forms.py           Formulare (WTForms)
  textutils.py       Markdown-Rendering + Helfer
  routes/            Blueprints (auth, wiki, admin, uploads, attachments, profile)
  templates/         Jinja2-Templates
  static/            CSS + JavaScript
config.py            Konfiguration (liest .env)
run.py               Einstiegspunkt
requirements.txt     Abhängigkeiten
install.ps1 / .sh    Lokale Installation
deploy*.py           Server-Deployment (optional)
```

---

## Aktualisieren

Nach dem Ziehen neuer Code-Stände:

```bash
pip install -r requirements.txt
flask ensure-schema     # ergänzt neue Tabellen/Spalten automatisch
```

Der Dienst (bzw. `python run.py`) danach neu starten.

---

## Lizenz

**GNU AGPL v3** – siehe [LICENSE](LICENSE).

Das bedeutet (wie bei DokuWiki, angepasst für Web-Apps): Der Code ist Open Source,
**aber Copyleft** – wer ihn weitergibt, verändert **oder als Netzwerk-Dienst betreibt**,
muss den (ggf. geänderten) Quellcode **offen unter AGPL** bereitstellen und die
Urheber nennen. „Nehmen, zumachen und als eigenes proprietäres Produkt verkaufen"
ist damit **nicht** erlaubt.

Copyright (C) 2026 MiniChaoz

> Hinweis zur AGPL: Da das Wiki als Web-Dienst läuft, sollte im Betrieb ein gut
> sichtbarer Link auf den Quellcode vorhanden sein (z. B. im Seitenfuß). Setze dazu
> die Umgebungsvariable `SOURCE_URL` auf deine Repository-Adresse.
