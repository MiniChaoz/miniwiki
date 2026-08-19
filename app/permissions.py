"""Decorators und Helfer fuer Zugriffskontrolle."""
from functools import wraps

from flask import abort
from flask_login import login_required, current_user


def admin_required(f):
    """Nur globale Admins."""
    @wraps(f)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return wrapped


def require_read(space):
    if not current_user.can_read(space):
        abort(403)


def require_write(space):
    if not current_user.can_write(space):
        abort(403)
