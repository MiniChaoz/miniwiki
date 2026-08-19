import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Sicherheit
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-me-immediately-in-production')

    # Datenbank (MySQL). Fuer lokale Tests kann auch SQLite genutzt werden:
    #   DATABASE_URL=sqlite:///wiki.db
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'mysql+pymysql://wiki:password@localhost/wiki'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CSRF-Schutz fuer alle Formulare
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Name/Label der Instanz (erscheint im Kopf des Wikis)
    WIKI_NAME = os.environ.get('WIKI_NAME', 'MiniWiki')

    # AGPL: Link zum Quellcode (im Seitenfuss angezeigt, falls gesetzt)
    SOURCE_URL = os.environ.get('SOURCE_URL', '')

    # Sichtbares Instanz-Label (z.B. "TEST"). Leer = Produktion (kein Banner).
    INSTANCE_LABEL = os.environ.get('INSTANCE_LABEL', '')

    # Cookie-Haertung (bei HTTPS auf True setzen via .env)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = os.environ.get('COOKIE_SECURE', 'false').lower() == 'true'

    # Uploads (Bilder + Datei-Anhaenge)
    # Maximale Upload-Groesse in MB (gilt fuer den ganzen Request)
    MAX_UPLOAD_MB = int(os.environ.get('MAX_UPLOAD_MB', '25'))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_MB * 1024 * 1024
    # Ablageort fuer eingebettete Bilder (Standard: instance/uploads).
    UPLOAD_DIR = os.environ.get('UPLOAD_DIR', '')
    # Ablageort fuer Datei-Anhaenge (Standard: instance/attachments).
    ATTACH_DIR = os.environ.get('ATTACH_DIR', '')
