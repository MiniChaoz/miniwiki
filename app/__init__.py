# MiniWiki – selbst gehostetes Wiki
# Copyright (C) 2026 MiniChaoz
# Lizenz: GNU Affero General Public License v3 – siehe LICENSE.
import os
import click
from flask import Flask
from flask.cli import with_appcontext

from config import Config
from .extensions import db, login_manager, migrate, csrf


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Upload-Verzeichnisse festlegen (Standard: instance/...) und anlegen
    upload_dir = app.config.get('UPLOAD_DIR') or os.path.join(app.instance_path, 'uploads')
    app.config['UPLOAD_DIR'] = upload_dir
    os.makedirs(upload_dir, exist_ok=True)
    attach_dir = app.config.get('ATTACH_DIR') or os.path.join(app.instance_path, 'attachments')
    app.config['ATTACH_DIR'] = attach_dir
    os.makedirs(attach_dir, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)

    # Modelle importieren, damit Migrationen/CLI sie kennen
    from . import models  # noqa: F401

    # Blueprints
    from .routes.auth import auth_bp
    from .routes.wiki import wiki_bp
    from .routes.admin import admin_bp
    from .routes.profile import profile_bp
    from .routes.uploads import uploads_bp
    from .routes.attachments import attachments_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(wiki_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(uploads_bp)
    app.register_blueprint(attachments_bp)

    # Fehlerseiten
    from flask import render_template

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    # Werte, die in jedem Template verfuegbar sind
    @app.context_processor
    def inject_globals():
        from flask import request
        from flask_login import current_user
        from .models import Space, Page

        nav_spaces = []
        nav_space_tree = []
        nav_tree = []
        nav_active_slug = None
        nav_active_page = None
        nav_space_drag = False
        nav_page_drag = False
        if current_user.is_authenticated:
            nav_space_drag = current_user.is_admin
            nav_spaces = current_user.readable_spaces()
            # Bereichs-Baum aufbauen: nur lesbare Bereiche, jeweils an den naechsten
            # lesbaren Elternbereich gehaengt (sonst als oberste Ebene).
            by_id = {s.id: s for s in nav_spaces}
            for s in nav_spaces:
                s.nav_children = []
            for s in sorted(nav_spaces, key=lambda x: (x.position, x.name.lower())):
                anc = s.parent
                while anc is not None and anc.id not in by_id:
                    anc = anc.parent
                if anc is None:
                    nav_space_tree.append(s)
                else:
                    by_id[anc.id].nav_children.append(s)
            # Seitenbaum des aktuell geoeffneten Bereichs aufbauen
            args = request.view_args or {}
            nav_active_slug = args.get('space_slug')
            nav_active_page = args.get('page_slug')
            if nav_active_slug and nav_active_slug in {s.slug for s in nav_spaces}:
                space = by_id[next(s.id for s in nav_spaces if s.slug == nav_active_slug)]
                pages = (Page.query.filter_by(space_id=space.id)
                         .order_by(Page.position, Page.title).all())
                nav_tree = [p for p in pages if p.parent_id is None]
                nav_page_drag = current_user.can_write(space)
        return {
            'WIKI_NAME': app.config.get('WIKI_NAME', 'MiniWiki'),
            'INSTANCE_LABEL': app.config.get('INSTANCE_LABEL', ''),
            'nav_spaces': nav_spaces,
            'nav_space_tree': nav_space_tree,
            'nav_tree': nav_tree,
            'nav_active_slug': nav_active_slug,
            'nav_active_page': nav_active_page,
            'nav_space_drag': nav_space_drag,
            'nav_page_drag': nav_page_drag,
        }

    _register_cli(app)
    return app


def _register_cli(app):
    @app.cli.command('init-db')
    @with_appcontext
    def init_db():
        """Erstellt alle Tabellen (fuer den ersten Start ohne Migrationen)."""
        db.create_all()
        click.echo('Tabellen wurden angelegt.')

    @app.cli.command('ensure-schema')
    @with_appcontext
    def ensure_schema():
        """Idempotentes Schema-Upgrade: neue Tabellen + fehlende Spalten anlegen."""
        from sqlalchemy import inspect, text
        # 1) Fehlende Tabellen (z.B. uploads) anlegen
        db.create_all()
        insp = inspect(db.engine)
        # 2) Fehlende Spalten nachziehen
        page_cols = [c['name'] for c in insp.get_columns('pages')]
        if 'parent_id' not in page_cols:
            db.session.execute(text('ALTER TABLE pages ADD COLUMN parent_id INTEGER NULL'))
            db.session.commit()
            click.echo('Spalte pages.parent_id ergaenzt.')
        space_cols = [c['name'] for c in insp.get_columns('spaces')]
        if 'parent_id' not in space_cols:
            db.session.execute(text('ALTER TABLE spaces ADD COLUMN parent_id INTEGER NULL'))
            db.session.commit()
            click.echo('Spalte spaces.parent_id ergaenzt.')
        # Manuelle Reihenfolge
        if 'position' not in page_cols:
            db.session.execute(text('ALTER TABLE pages ADD COLUMN position INTEGER NOT NULL DEFAULT 0'))
            db.session.commit()
            click.echo('Spalte pages.position ergaenzt.')
        if 'position' not in space_cols:
            db.session.execute(text('ALTER TABLE spaces ADD COLUMN position INTEGER NOT NULL DEFAULT 0'))
            db.session.commit()
            click.echo('Spalte spaces.position ergaenzt.')
        click.echo('Schema ist aktuell.')

    @app.cli.command('seed-templates')
    @with_appcontext
    def seed_templates():
        """Legt nuetzliche Standard-Vorlagen an (nur, wenn noch nicht vorhanden)."""
        from .models import PageTemplate
        defaults = [
            ('Stoerungs-Anleitung', 'Schritt-fuer-Schritt zur Loesung eines Problems',
             'Stoerung: ',
             '## Symptom\n\nWas tritt auf?\n\n## Betroffen\n\nSystem/Kunde/Gerät.\n\n'
             '## Ursache\n\n## Loesung\n\n1. Schritt eins\n2. Schritt zwei\n\n'
             '## Vorbeugung\n\n## Verweise\n\n- Ticket: \n- Weitere Doku: '),
            ('Kunden-Steckbrief', 'Uebersicht zu einem Kunden',
             'Kunde: ',
             '## Kontakt\n\n- Ansprechpartner: \n- Telefon: \n- E-Mail: \n\n'
             '## Systeme & Umgebung\n\n| System | Details |\n|---|---|\n|  |  |\n\n'
             '## Zugaenge\n\n> Passwoerter gehoeren in den Passwortmanager – hier nur Verweise!\n\n'
             '## Besonderheiten / Notizen\n\n## Verweise\n\n- Tickets: '),
            ('Server-Doku', 'Dokumentation eines Servers/Geraets',
             'Server: ',
             '## Eckdaten\n\n| Feld | Wert |\n|---|---|\n| Hostname |  |\n| IP |  |\n'
             '| Betriebssystem |  |\n| Standort |  |\n| Zweck |  |\n\n'
             '## Dienste / Rollen\n\n- \n\n## Wartung\n\n- Backups: \n- Updates: \n\n'
             '## Bekannte Probleme\n\n## Verweise'),
            ('Onboarding-Checkliste', 'Checkliste fuer neue Mitarbeitende/Kunden',
             'Onboarding: ',
             '## Vorbereitung\n\n- [ ] Benutzerkonto anlegen\n- [ ] Hardware bereitstellen\n'
             '- [ ] Zugaenge einrichten\n\n## Am ersten Tag\n\n- [ ] Einweisung\n- [ ] '
             'Software installieren\n\n## Nachbereitung\n\n- [ ] Dokumentation ablegen\n- [ ] Ticket schliessen'),
        ]
        added = 0
        for name, desc, hint, content in defaults:
            if not PageTemplate.query.filter_by(name=name).first():
                db.session.add(PageTemplate(name=name, description=desc,
                                            title_hint=hint, content=content))
                added += 1
        db.session.commit()
        click.echo(f'{added} Vorlage(n) angelegt (vorhandene uebersprungen).')

    @app.cli.command('create-admin')
    @click.option('--username', prompt=True)
    @click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option('--email', default='', help='Optionale E-Mail-Adresse.')
    @with_appcontext
    def create_admin(username, password, email):
        """Legt einen Administrator an (oder macht einen bestehenden Nutzer zum Admin)."""
        from .models import User, ROLE_ADMIN
        user = User.query.filter_by(username=username).first()
        if user:
            user.role = ROLE_ADMIN
            user.is_active = True
            if password:
                user.set_password(password)
            click.echo(f'Bestehender Nutzer "{username}" ist jetzt Admin.')
        else:
            user = User(
                username=username,
                email=email or None,
                display_name=username,
                role=ROLE_ADMIN,
                is_active=True,
            )
            user.set_password(password)
            db.session.add(user)
            click.echo(f'Admin "{username}" wurde angelegt.')
        db.session.commit()

    @app.cli.command('seed-demo')
    @with_appcontext
    def seed_demo():
        """Legt Beispiel-Bereiche und eine Startseite an."""
        from .models import Space, Page, ACCESS_READ, ACCESS_NONE
        if Space.query.first():
            click.echo('Es gibt bereits Bereiche – Seed uebersprungen.')
            return
        allgemein = Space(
            slug='allgemein', name='Allgemein',
            description='Fuer alle sichtbar – Ankuendigungen und Grundlagen.',
            default_access=ACCESS_READ,
        )
        intern = Space(
            slug='intern', name='Intern',
            description='Nur fuer Berechtigte.',
            default_access=ACCESS_NONE,
        )
        db.session.add_all([allgemein, intern])
        db.session.flush()
        db.session.add(Page(
            space_id=allgemein.id, slug='willkommen', title='Willkommen',
            content=(
                '# Willkommen im Wiki\n\n'
                'Das hier ist deine **Startseite**. Bearbeite sie ueber den '
                'Button *Bearbeiten* oben rechts.\n\n'
                '## Erste Schritte\n\n'
                '- Lege links neue Seiten an\n'
                '- Formatiere mit Markdown oder im WYSIWYG-Modus\n'
                '- Steuere Zugriffe unter *Verwaltung*\n'
            ),
        ))
        db.session.commit()
        click.echo('Demo-Bereiche und Startseite wurden angelegt.')
