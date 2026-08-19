"""
Datenmodelle fuer das Wiki.

Rechte-Modell (Hybrid aus globaler Rolle + Bereichs-Zugriff):

  Globale Rolle (User.role) = Obergrenze fuer den Nutzer:
    - viewer : darf ueberall hoechstens LESEN
    - editor : darf LESEN und SCHREIBEN, wo der Bereich es erlaubt
    - admin  : darf alles + Nutzer/Bereiche verwalten

  Bereich (Space.default_access) = Standardzugriff fuer alle eingeloggten
  Nutzer ohne eigene Ausnahme: none / read / write

  Mitgliedschaft (SpaceMembership.access) = Ausnahme pro Nutzer je Bereich,
  uebersteuert den Standardzugriff: read / write

  Effektiv:
    lesen    = admin ODER (Bereich/Ausnahme >= read)
    schreiben= (Rolle in editor/admin) UND (admin ODER Bereich/Ausnahme == write)
"""
from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from .extensions import db, login_manager


# --- Konstanten -------------------------------------------------------------

ROLE_VIEWER = 'viewer'
ROLE_EDITOR = 'editor'
ROLE_ADMIN = 'admin'

ROLE_LABELS = {
    ROLE_VIEWER: 'Leser',
    ROLE_EDITOR: 'Redakteur',
    ROLE_ADMIN: 'Admin',
}

ACCESS_NONE = 'none'
ACCESS_READ = 'read'
ACCESS_WRITE = 'write'

ACCESS_LABELS = {
    ACCESS_NONE: 'Kein Zugriff',
    ACCESS_READ: 'Lesen',
    ACCESS_WRITE: 'Schreiben',
}

# Rangfolge fuer Vergleiche
_ACCESS_RANK = {ACCESS_NONE: 0, ACCESS_READ: 1, ACCESS_WRITE: 2}


# --- Nutzer -----------------------------------------------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=True)
    display_name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default=ROLE_VIEWER)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    memberships = db.relationship(
        'SpaceMembership', back_populates='user',
        cascade='all, delete-orphan', lazy='selectin'
    )

    # -- Passwort --
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # -- Rollen-Kurzfragen --
    @property
    def is_admin(self):
        return self.role == ROLE_ADMIN

    @property
    def can_edit_anywhere(self):
        return self.role in (ROLE_EDITOR, ROLE_ADMIN)

    @property
    def role_label(self):
        return ROLE_LABELS.get(self.role, self.role)

    @property
    def name(self):
        return self.display_name or self.username

    # -- Bereichs-Rechte --
    def _membership_for(self, space):
        for m in self.memberships:
            if m.space_id == space.id:
                return m
        return None

    def effective_access(self, space):
        """Effektiver Zugriff (none/read/write) dieses Nutzers auf einen Bereich."""
        if self.is_admin:
            return ACCESS_WRITE
        m = self._membership_for(space)
        base = m.access if m else space.default_access
        # Rolle deckelt: Leser bekommt maximal 'read'
        if not self.can_edit_anywhere and base == ACCESS_WRITE:
            return ACCESS_READ
        return base

    def can_read(self, space):
        return _ACCESS_RANK[self.effective_access(space)] >= _ACCESS_RANK[ACCESS_READ]

    def can_write(self, space):
        return _ACCESS_RANK[self.effective_access(space)] >= _ACCESS_RANK[ACCESS_WRITE]

    def readable_spaces(self):
        """Alle Bereiche, die dieser Nutzer lesen darf (sortiert)."""
        spaces = Space.query.order_by(Space.name).all()
        return [s for s in spaces if self.can_read(s)]

    def __repr__(self):
        return f'<User {self.username}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# --- Bereiche (Spaces) ------------------------------------------------------

class Space(db.Model):
    __tablename__ = 'spaces'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('spaces.id', ondelete='SET NULL'), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    # Standardzugriff fuer eingeloggte Nutzer ohne eigene Mitgliedschaft
    default_access = db.Column(db.String(10), nullable=False, default=ACCESS_NONE)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    pages = db.relationship(
        'Page', back_populates='space',
        cascade='all, delete-orphan', lazy='selectin'
    )
    memberships = db.relationship(
        'SpaceMembership', back_populates='space',
        cascade='all, delete-orphan', lazy='selectin'
    )
    parent = db.relationship('Space', remote_side=[id], backref='children')

    @property
    def default_access_label(self):
        return ACCESS_LABELS.get(self.default_access, self.default_access)

    def descendant_ids(self):
        """IDs aller Unterbereiche (rekursiv) – verhindert Zyklen bei der Elternwahl."""
        ids = []
        stack = list(self.children)
        while stack:
            child = stack.pop()
            ids.append(child.id)
            stack.extend(child.children)
        return ids

    def __repr__(self):
        return f'<Space {self.slug}>'


class SpaceMembership(db.Model):
    __tablename__ = 'space_memberships'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'space_id', name='uq_user_space'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    space_id = db.Column(db.Integer, db.ForeignKey('spaces.id', ondelete='CASCADE'), nullable=False)
    access = db.Column(db.String(10), nullable=False, default=ACCESS_READ)

    user = db.relationship('User', back_populates='memberships')
    space = db.relationship('Space', back_populates='memberships')

    @property
    def access_label(self):
        return ACCESS_LABELS.get(self.access, self.access)


# --- Seiten -----------------------------------------------------------------

class Page(db.Model):
    __tablename__ = 'pages'
    __table_args__ = (
        db.UniqueConstraint('space_id', 'slug', name='uq_space_slug'),
    )

    id = db.Column(db.Integer, primary_key=True)
    space_id = db.Column(db.Integer, db.ForeignKey('spaces.id', ondelete='CASCADE'), nullable=False)
    slug = db.Column(db.String(160), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    parent_id = db.Column(db.Integer, db.ForeignKey('pages.id', ondelete='SET NULL'), nullable=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    space = db.relationship('Space', back_populates='pages')
    parent = db.relationship('Page', remote_side=[id], backref='children')
    tags = db.relationship('Tag', secondary='page_tags', backref='pages', lazy='selectin')
    attachments = db.relationship(
        'Attachment', back_populates='page',
        cascade='all, delete-orphan', lazy='selectin',
        order_by='Attachment.created_at.desc()'
    )
    revisions = db.relationship(
        'PageRevision', back_populates='page',
        cascade='all, delete-orphan',
        order_by='PageRevision.created_at.desc()', lazy='selectin'
    )
    author = db.relationship('User', foreign_keys=[created_by])
    editor = db.relationship('User', foreign_keys=[updated_by])

    def descendant_ids(self):
        """IDs aller Unterseiten (rekursiv) – verhindert Zyklen bei der Elternwahl."""
        ids = []
        stack = list(self.children)
        while stack:
            child = stack.pop()
            ids.append(child.id)
            stack.extend(child.children)
        return ids

    def __repr__(self):
        return f'<Page {self.space_id}/{self.slug}>'


class PageRevision(db.Model):
    """Eine gespeicherte Version einer Seite (Verlauf)."""
    __tablename__ = 'page_revisions'

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False, default='')
    comment = db.Column(db.String(255), nullable=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    page = db.relationship('Page', back_populates='revisions')
    author = db.relationship('User')


class Upload(db.Model):
    """Hochgeladene Datei (Bild), die in Seiten eingebettet werden kann."""
    __tablename__ = 'uploads'

    id = db.Column(db.Integer, primary_key=True)
    stored_name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=True)
    mime = db.Column(db.String(80), nullable=True)
    size = db.Column(db.Integer, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User')


# --- Schlagworte (Tags) -----------------------------------------------------

# Verknuepfungstabelle Seite <-> Tag (n:m)
page_tags = db.Table(
    'page_tags',
    db.Column('page_id', db.Integer, db.ForeignKey('pages.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True),
)


class Tag(db.Model):
    __tablename__ = 'tags'

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)

    def __repr__(self):
        return f'<Tag {self.slug}>'


# --- Seiten-Vorlagen --------------------------------------------------------

class PageTemplate(db.Model):
    """Wiederverwendbare Vorlage fuer neue Seiten (vom Admin gepflegt)."""
    __tablename__ = 'page_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    title_hint = db.Column(db.String(200), nullable=True)
    content = db.Column(db.Text, nullable=False, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# --- Datei-Anhaenge an Seiten -----------------------------------------------

class Attachment(db.Model):
    """Beliebige Datei (PDF, Log, Config, ...), die an eine Seite gehaengt ist."""
    __tablename__ = 'attachments'

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False)
    stored_name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    original_name = db.Column(db.String(255), nullable=False)
    mime = db.Column(db.String(120), nullable=True)
    size = db.Column(db.Integer, nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    page = db.relationship('Page', back_populates='attachments')
    uploader = db.relationship('User')

    @property
    def size_human(self):
        n = self.size or 0
        for unit in ('B', 'KB', 'MB', 'GB'):
            if n < 1024:
                return f'{n:.0f} {unit}' if unit == 'B' else f'{n:.1f} {unit}'
            n /= 1024
        return f'{n:.1f} TB'


# --- Favoriten & Verlauf (pro Nutzer) --------------------------------------

class Favorite(db.Model):
    __tablename__ = 'favorites'
    __table_args__ = (db.UniqueConstraint('user_id', 'page_id', name='uq_fav_user_page'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    page = db.relationship('Page')


class Visit(db.Model):
    """Zuletzt angesehene Seite pro Nutzer (ein Eintrag je Seite, aktualisiert)."""
    __tablename__ = 'visits'
    __table_args__ = (db.UniqueConstraint('user_id', 'page_id', name='uq_visit_user_page'),)

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id', ondelete='CASCADE'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    page = db.relationship('Page')
