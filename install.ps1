# MiniWiki – lokale Installation (Windows / PowerShell)
# Aufruf:  .\install.ps1
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

Write-Host "== MiniWiki Installation ==" -ForegroundColor Cyan

# 1) Virtuelle Umgebung + Abhaengigkeiten
if (-not (Test-Path venv)) { python -m venv venv }
.\venv\Scripts\python -m pip install --upgrade pip wheel
.\venv\Scripts\python -m pip install -r requirements.txt

# 2) .env anlegen (falls noch nicht vorhanden) – Standard: SQLite
if (-not (Test-Path .env)) {
  $secret = .\venv\Scripts\python -c "import secrets;print(secrets.token_hex(32))"
  @"
SECRET_KEY=$secret
DATABASE_URL=sqlite:///wiki.db
WIKI_NAME=MiniWiki
INSTANCE_LABEL=
COOKIE_SECURE=false
"@ | Set-Content -Encoding utf8 .env
  Write-Host ".env wurde erstellt (SQLite)." -ForegroundColor Green
} else {
  Write-Host ".env existiert bereits – wird nicht ueberschrieben." -ForegroundColor Yellow
}

# 3) Datenbank + Admin
$env:FLASK_APP = 'run.py'
.\venv\Scripts\flask init-db
.\venv\Scripts\flask ensure-schema
.\venv\Scripts\flask seed-templates
Write-Host "`nLege jetzt den Administrator an:" -ForegroundColor Cyan
.\venv\Scripts\flask create-admin

Write-Host "`nFertig! Starten mit:" -ForegroundColor Green
Write-Host "    .\venv\Scripts\python run.py"
Write-Host "Dann im Browser: http://127.0.0.1:5001"
