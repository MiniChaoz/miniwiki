#!/usr/bin/env bash
# MiniWiki – lokale Installation (Linux / macOS)
# Aufruf:  bash install.sh
set -e
cd "$(dirname "$0")"

echo "== MiniWiki Installation =="

# 1) Virtuelle Umgebung + Abhaengigkeiten
if [ ! -d venv ]; then python3 -m venv venv; fi
./venv/bin/python -m pip install --upgrade pip wheel
./venv/bin/python -m pip install -r requirements.txt

# 2) .env anlegen (falls noch nicht vorhanden) – Standard: SQLite
if [ ! -f .env ]; then
  SECRET=$(./venv/bin/python -c "import secrets;print(secrets.token_hex(32))")
  cat > .env <<EOF
SECRET_KEY=$SECRET
DATABASE_URL=sqlite:///wiki.db
WIKI_NAME=MiniWiki
INSTANCE_LABEL=
COOKIE_SECURE=false
EOF
  echo ".env wurde erstellt (SQLite)."
else
  echo ".env existiert bereits – wird nicht ueberschrieben."
fi

# 3) Datenbank + Admin
export FLASK_APP=run.py
./venv/bin/flask init-db
./venv/bin/flask ensure-schema
./venv/bin/flask seed-templates
echo ""
echo "Lege jetzt den Administrator an:"
./venv/bin/flask create-admin

echo ""
echo "Fertig! Starten mit:"
echo "    ./venv/bin/python run.py"
echo "Dann im Browser: http://127.0.0.1:5001"
