"""Bild-Uploads: Annahme, sichere Speicherung, geschuetzte Auslieferung."""
import os
import secrets

from flask import (
    Blueprint, request, jsonify, current_app, send_from_directory, abort,
)
from flask_login import login_required, current_user

from ..extensions import db
from ..models import Upload

uploads_bp = Blueprint('uploads', __name__)

# Erlaubte Bildtypen (SVG bewusst NICHT – XSS-Risiko)
_ALLOWED_EXT = {'png': 'image/png', 'jpg': 'image/jpeg', 'jpeg': 'image/jpeg',
                'gif': 'image/gif', 'webp': 'image/webp'}

# Magic-Bytes zur echten Typpruefung (nicht nur Dateiendung)
_SIGNATURES = {
    'png':  [b'\x89PNG\r\n\x1a\n'],
    'jpg':  [b'\xff\xd8\xff'],
    'jpeg': [b'\xff\xd8\xff'],
    'gif':  [b'GIF87a', b'GIF89a'],
    'webp': [b'RIFF'],   # RIFF....WEBP – zusaetzlich unten geprueft
}


def _valid_signature(ext, head):
    for sig in _SIGNATURES.get(ext, []):
        if head.startswith(sig):
            if ext == 'webp':
                return head[8:12] == b'WEBP'
            return True
    return False


@uploads_bp.route('/upload/image', methods=['POST'])
@login_required
def upload_image():
    # Nur wer irgendwo schreiben darf (Redakteur/Admin) darf hochladen
    if not current_user.can_edit_anywhere:
        abort(403)

    file = request.files.get('image') or request.files.get('file')
    if not file or not file.filename:
        return jsonify(error='Keine Datei erhalten.'), 400

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in _ALLOWED_EXT:
        return jsonify(error='Nur PNG, JPG, GIF oder WEBP erlaubt.'), 400

    head = file.stream.read(16)
    file.stream.seek(0)
    if not _valid_signature(ext, head):
        return jsonify(error='Datei ist kein gueltiges Bild.'), 400

    stored_name = secrets.token_hex(16) + '.' + ext
    dest = os.path.join(current_app.config['UPLOAD_DIR'], stored_name)
    file.save(dest)
    size = os.path.getsize(dest)

    db.session.add(Upload(
        stored_name=stored_name,
        original_name=file.filename[:255],
        mime=_ALLOWED_EXT[ext],
        size=size,
        uploaded_by=current_user.id,
    ))
    db.session.commit()

    from flask import url_for
    return jsonify(url=url_for('uploads.serve', name=stored_name))


@uploads_bp.route('/uploads/<name>')
@login_required
def serve(name):
    # Nur eingeloggte Nutzer sehen Uploads. send_from_directory schuetzt vor
    # Pfad-Traversal; zusaetzlich pruefen wir den Namen gegen die DB.
    if Upload.query.filter_by(stored_name=name).first() is None:
        abort(404)
    return send_from_directory(current_app.config['UPLOAD_DIR'], name)
