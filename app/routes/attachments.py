"""Datei-Anhaenge an Seiten: Upload, geschuetzter Download, Loeschen."""
import os
import secrets

from flask import (
    Blueprint, request, redirect, url_for, flash, abort, current_app, send_from_directory,
)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Space, Page, Attachment
from ..forms import ConfirmForm
from ..permissions import require_read, require_write

attachments_bp = Blueprint('attachments', __name__)

# Erlaubte Endungen (bewusst KEINE ausfuehrbaren/aktiven Formate wie exe/js/html/svg)
ALLOWED_EXT = {
    'pdf', 'txt', 'log', 'csv', 'md', 'json', 'xml', 'yml', 'yaml',
    'cfg', 'conf', 'ini', 'reg',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp', 'rtf',
    'zip', '7z', 'tar', 'gz',
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff',
    'msg', 'eml', 'pcap',
}


def _get_page(space_slug, page_slug):
    space = Space.query.filter_by(slug=space_slug).first()
    if space is None:
        abort(404)
    page = Page.query.filter_by(space_id=space.id, slug=page_slug).first()
    if page is None:
        abort(404)
    return space, page


@attachments_bp.route('/space/<space_slug>/<page_slug>/attach', methods=['POST'])
@login_required
def upload(space_slug, page_slug):
    space, page = _get_page(space_slug, page_slug)
    require_write(space)

    file = request.files.get('file')
    if not file or not file.filename:
        flash('Keine Datei ausgewaehlt.', 'warning')
        return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_EXT:
        flash(f'Dateityp „.{ext}" ist nicht erlaubt.', 'danger')
        return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))

    stored_name = secrets.token_hex(16) + '.' + ext
    dest = os.path.join(current_app.config['ATTACH_DIR'], stored_name)
    file.save(dest)

    db.session.add(Attachment(
        page_id=page.id,
        stored_name=stored_name,
        original_name=secure_filename(file.filename) or ('datei.' + ext),
        mime=file.mimetype,
        size=os.path.getsize(dest),
        uploaded_by=current_user.id,
    ))
    db.session.commit()
    flash('Anhang wurde hochgeladen.', 'success')
    return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))


@attachments_bp.route('/attachments/<int:att_id>/download')
@login_required
def download(att_id):
    att = db.session.get(Attachment, att_id) or abort(404)
    require_read(att.page.space)
    # Immer als Download ausliefern (kein Inline-Rendering).
    return send_from_directory(
        current_app.config['ATTACH_DIR'], att.stored_name,
        as_attachment=True, download_name=att.original_name,
    )


@attachments_bp.route('/attachments/<int:att_id>/delete', methods=['POST'])
@login_required
def delete(att_id):
    att = db.session.get(Attachment, att_id) or abort(404)
    space = att.page.space
    require_write(space)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    page_slug = att.page.slug
    try:
        os.remove(os.path.join(current_app.config['ATTACH_DIR'], att.stored_name))
    except OSError:
        pass
    db.session.delete(att)
    db.session.commit()
    flash('Anhang wurde geloescht.', 'info')
    return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page_slug))
