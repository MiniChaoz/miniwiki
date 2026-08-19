import io
import os

from datetime import datetime

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
    current_app, Response, jsonify,
)
from flask_login import login_required, current_user
from sqlalchemy import or_

from ..extensions import db
from ..models import Space, Page, PageRevision, Tag, PageTemplate, Favorite, Visit
from ..forms import PageForm, ConfirmForm, MovePageForm
from ..permissions import require_read, require_write
from ..textutils import render_markdown, slugify, excerpt, split_tags, highlight

wiki_bp = Blueprint('wiki', __name__)


# -- Helfer ------------------------------------------------------------------

def _get_space_or_404(space_slug):
    space = Space.query.filter_by(slug=space_slug).first()
    if space is None:
        abort(404)
    return space


def _get_page_or_404(space, page_slug):
    page = Page.query.filter_by(space_id=space.id, slug=page_slug).first()
    if page is None:
        abort(404)
    return page


def _unique_page_slug(space, title, exclude_id=None):
    base = slugify(title)
    slug = base
    i = 2
    while True:
        existing = Page.query.filter_by(space_id=space.id, slug=slug).first()
        if existing is None or existing.id == exclude_id:
            return slug
        slug = f'{base}-{i}'
        i += 1


def _parent_choices(space, exclude=None):
    """Auswahlliste moeglicher Elternseiten (eingerueckt), ohne die Seite selbst
    und ihre Unterseiten (verhindert Zyklen)."""
    blocked = set()
    if exclude is not None:
        blocked = set(exclude.descendant_ids()) | {exclude.id}
    pages = Page.query.filter_by(space_id=space.id).order_by(Page.position, Page.title).all()
    by_parent = {}
    for p in pages:
        by_parent.setdefault(p.parent_id, []).append(p)
    choices = [(0, '— keine (oberste Ebene) —')]

    def walk(parent_id, depth):
        for p in by_parent.get(parent_id, []):
            if p.id in blocked:
                continue
            choices.append((p.id, ('  ' * depth) + '↳ ' + p.title if depth else p.title))
            walk(p.id, depth + 1)

    walk(None, 0)
    return choices


def _sync_tags(page, tags_string):
    """Setzt die Tags einer Seite anhand des Komma-Strings (legt neue Tags an)."""
    names = split_tags(tags_string)
    tags = []
    for name in names:
        slug = slugify(name, fallback='tag')
        tag = Tag.query.filter_by(slug=slug).first()
        if tag is None:
            tag = Tag(slug=slug, name=name)
            db.session.add(tag)
        tags.append(tag)
    page.tags = tags


def _cleanup_orphan_tags():
    """Entfernt Tags, die an keiner Seite mehr haengen."""
    for tag in Tag.query.all():
        if not tag.pages:
            db.session.delete(tag)


def _record_visit(page):
    """Merkt sich die zuletzt angesehene Seite (ein Eintrag je Nutzer/Seite)."""
    v = Visit.query.filter_by(user_id=current_user.id, page_id=page.id).first()
    if v:
        v.viewed_at = datetime.utcnow()
    else:
        db.session.add(Visit(user_id=current_user.id, page_id=page.id))
    db.session.commit()


def _is_favorite(page):
    return Favorite.query.filter_by(user_id=current_user.id, page_id=page.id).first() is not None


def _next_position(space_id, parent_id):
    mx = db.session.query(db.func.max(Page.position)).filter_by(
        space_id=space_id, parent_id=parent_id).scalar()
    return (mx or 0) + 1


def _next_space_position(parent_id):
    mx = db.session.query(db.func.max(Space.position)).filter_by(parent_id=parent_id).scalar()
    return (mx or 0) + 1


def _move_page_subtree(page, target_space, new_parent_id):
    """Verschiebt eine Seite samt allen Unterseiten in einen (evtl. anderen) Bereich."""
    if target_space.id != page.space_id:
        subtree = [page]
        for pid in page.descendant_ids():
            p = db.session.get(Page, pid)
            if p:
                subtree.append(p)
        for p in subtree:
            p.space_id = target_space.id
            clash = Page.query.filter(Page.space_id == target_space.id,
                                      Page.slug == p.slug, Page.id != p.id).first()
            if clash:
                p.slug = _unique_page_slug(target_space, p.title, exclude_id=p.id)
    page.parent_id = new_parent_id
    page.position = _next_position(target_space.id, new_parent_id)


def _reorder(model, item, direction, **sibling_filter):
    """Verschiebt ein Element unter seinen Geschwistern eine Stufe hoch/runter."""
    sibs = (model.query.filter_by(**sibling_filter)
            .order_by(model.position, model.id).all())
    for i, s in enumerate(sibs):
        s.position = i
    idx = next((i for i, s in enumerate(sibs) if s.id == item.id), None)
    if idx is None:
        return
    j = idx - 1 if direction == 'up' else idx + 1
    if 0 <= j < len(sibs):
        sibs[idx].position, sibs[j].position = sibs[j].position, sibs[idx].position


# -- Uebersicht --------------------------------------------------------------

@wiki_bp.route('/')
@login_required
def index():
    spaces = current_user.readable_spaces()
    readable_ids = [s.id for s in spaces]
    readable_set = set(readable_ids)

    # Kacheln: nur Bereiche der obersten Ebene (Einstiegspunkte), mit Seitenzahl
    # ueber den ganzen Teilbaum.
    all_spaces = Space.query.all()
    children_map = {}
    for s in all_spaces:
        children_map.setdefault(s.parent_id, []).append(s)

    def subtree_ids(space):
        ids = [space.id]
        stack = list(children_map.get(space.id, []))
        while stack:
            c = stack.pop()
            ids.append(c.id)
            stack.extend(children_map.get(c.id, []))
        return ids

    top_tiles = []
    for s in sorted([sp for sp in spaces if sp.parent_id is None], key=lambda x: (x.position, x.name.lower())):
        ids = subtree_ids(s)
        count = Page.query.filter(Page.space_id.in_(ids)).count()
        sub = sorted([c for c in children_map.get(s.id, []) if c.id in readable_set],
                     key=lambda x: (x.position, x.name.lower()))
        top_tiles.append({'space': s, 'count': count, 'subspaces': sub})

    favorites = []
    recents = []
    recent = []
    if readable_ids:
        favorites = [
            f.page for f in (
                Favorite.query.filter_by(user_id=current_user.id)
                .order_by(Favorite.created_at.desc()).limit(12).all())
            if f.page and f.page.space_id in readable_set
        ]
        recents = [
            v.page for v in (
                Visit.query.filter_by(user_id=current_user.id)
                .order_by(Visit.viewed_at.desc()).limit(8).all())
            if v.page and v.page.space_id in readable_set
        ]
        recent = (
            Page.query.filter(Page.space_id.in_(readable_ids))
            .order_by(Page.updated_at.desc()).limit(8).all()
        )
    return render_template('wiki/index.html', top_tiles=top_tiles,
                           favorites=favorites, recents=recents,
                           recent=recent, excerpt=excerpt)


# -- Bereich -----------------------------------------------------------------

@wiki_bp.route('/space/<space_slug>')
@login_required
def space(space_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    pages = (
        Page.query.filter_by(space_id=space.id)
        .order_by(Page.position, Page.title)
        .all()
    )
    child_spaces = sorted(
        [c for c in space.children if current_user.can_read(c)],
        key=lambda s: (s.position, s.name.lower())
    )
    return render_template(
        'wiki/space.html',
        space=space, pages=pages, child_spaces=child_spaces,
        can_write=current_user.can_write(space),
        can_admin=current_user.is_admin,
        excerpt=excerpt,
    )


# -- Seite ansehen -----------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>')
@login_required
def page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    # Ahnenkette (fuer Brotkrumen), von oben nach unten
    ancestors = []
    node = page.parent
    seen = set()
    while node is not None and node.id not in seen:
        seen.add(node.id)
        ancestors.append(node)
        node = node.parent
    ancestors.reverse()
    children = sorted(page.children, key=lambda p: (p.position, p.title.lower()))
    _record_visit(page)
    return render_template(
        'wiki/page.html',
        space=space, page=page, ancestors=ancestors, children=children,
        body_html=render_markdown(page.content),
        can_write=current_user.can_write(space),
        is_favorite=_is_favorite(page),
    )


# -- Seite anlegen -----------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/new', methods=['GET', 'POST'])
@login_required
def new_page(space_slug):
    space = _get_space_or_404(space_slug)
    require_write(space)
    form = PageForm()
    form.parent_id.choices = _parent_choices(space)
    templates = PageTemplate.query.order_by(PageTemplate.name).all()
    if request.method == 'GET':
        # Vorbelegung, wenn per "+ Unterseite" aufgerufen
        try:
            form.parent_id.data = int(request.args.get('parent', 0))
        except (TypeError, ValueError):
            form.parent_id.data = 0
        # Vorbelegung aus einer Vorlage
        tpl_id = request.args.get('template')
        if tpl_id:
            tpl = db.session.get(PageTemplate, int(tpl_id)) if tpl_id.isdigit() else None
            if tpl:
                form.content.data = tpl.content
                if tpl.title_hint and not form.title.data:
                    form.title.data = tpl.title_hint
    if form.validate_on_submit():
        slug = _unique_page_slug(space, form.title.data)
        parent_id = form.parent_id.data or None
        if parent_id and not Page.query.filter_by(id=parent_id, space_id=space.id).first():
            parent_id = None
        page = Page(
            space_id=space.id, slug=slug,
            title=form.title.data.strip(),
            content=form.content.data or '',
            parent_id=parent_id,
            created_by=current_user.id, updated_by=current_user.id,
        )
        db.session.add(page)
        db.session.flush()
        _sync_tags(page, form.tags.data)
        db.session.add(PageRevision(
            page_id=page.id, title=page.title, content=page.content,
            comment=form.comment.data or 'Erstellt', author_id=current_user.id,
        ))
        db.session.commit()
        flash('Seite wurde angelegt.', 'success')
        return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))
    return render_template('wiki/edit.html', space=space, form=form, page=None, templates=templates)


# -- Seite bearbeiten --------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>/edit', methods=['GET', 'POST'])
@login_required
def edit_page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_write(space)
    page = _get_page_or_404(space, page_slug)
    form = PageForm(obj=page)
    form.parent_id.choices = _parent_choices(space, exclude=page)
    if request.method == 'GET':
        form.parent_id.data = page.parent_id or 0
        form.tags.data = ', '.join(t.name for t in page.tags)
    if form.validate_on_submit():
        new_parent = form.parent_id.data or None
        # Ungueltige/zyklische Elternwahl abfangen
        if new_parent and (new_parent == page.id or new_parent in page.descendant_ids()
                           or not Page.query.filter_by(id=new_parent, space_id=space.id).first()):
            new_parent = page.parent_id
        changed = (form.title.data.strip() != page.title) or ((form.content.data or '') != page.content)
        page.title = form.title.data.strip()
        page.content = form.content.data or ''
        page.parent_id = new_parent
        page.updated_by = current_user.id
        _sync_tags(page, form.tags.data)
        if changed:
            db.session.add(PageRevision(
                page_id=page.id, title=page.title, content=page.content,
                comment=form.comment.data or 'Bearbeitet', author_id=current_user.id,
            ))
        db.session.commit()
        _cleanup_orphan_tags()
        db.session.commit()
        flash('Seite wurde gespeichert.', 'success')
        return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))
    return render_template('wiki/edit.html', space=space, form=form, page=page, templates=None)


# -- Seite loeschen ----------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>/delete', methods=['POST'])
@login_required
def delete_page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_write(space)
    page = _get_page_or_404(space, page_slug)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    db.session.delete(page)
    db.session.commit()
    _cleanup_orphan_tags()
    db.session.commit()
    flash('Seite wurde geloescht.', 'info')
    return redirect(url_for('wiki.space', space_slug=space.slug))


# -- Verlauf -----------------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>/history')
@login_required
def history(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    return render_template('wiki/history.html', space=space, page=page)


@wiki_bp.route('/space/<space_slug>/<page_slug>/rev/<int:rev_id>')
@login_required
def revision(space_slug, page_slug, rev_id):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    rev = db.session.get(PageRevision, rev_id)
    if rev is None or rev.page_id != page.id:
        abort(404)
    return render_template(
        'wiki/revision.html',
        space=space, page=page, rev=rev,
        body_html=render_markdown(rev.content),
        can_write=current_user.can_write(space),
    )


@wiki_bp.route('/space/<space_slug>/<page_slug>/rev/<int:rev_id>/restore', methods=['POST'])
@login_required
def restore_revision(space_slug, page_slug, rev_id):
    space = _get_space_or_404(space_slug)
    require_write(space)
    page = _get_page_or_404(space, page_slug)
    rev = db.session.get(PageRevision, rev_id)
    if rev is None or rev.page_id != page.id:
        abort(404)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    page.title = rev.title
    page.content = rev.content
    page.updated_by = current_user.id
    db.session.add(PageRevision(
        page_id=page.id, title=page.title, content=page.content,
        comment=f'Wiederhergestellt aus Version #{rev.id}', author_id=current_user.id,
    ))
    db.session.commit()
    flash('Version wurde wiederhergestellt.', 'success')
    return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))


# -- Suche -------------------------------------------------------------------

@wiki_bp.route('/changes')
@login_required
def changes():
    readable_ids = [s.id for s in current_user.readable_spaces()]
    revs = []
    if readable_ids:
        revs = (
            PageRevision.query
            .join(Page, PageRevision.page_id == Page.id)
            .filter(Page.space_id.in_(readable_ids))
            .order_by(PageRevision.created_at.desc())
            .limit(100)
            .all()
        )
    return render_template('wiki/changes.html', revs=revs)


@wiki_bp.route('/tags')
@login_required
def tags():
    readable_ids = [s.id for s in current_user.readable_spaces()]
    entries = []
    for tag in Tag.query.order_by(Tag.name).all():
        count = sum(1 for p in tag.pages if p.space_id in readable_ids)
        if count:
            entries.append((tag, count))
    return render_template('wiki/tags.html', entries=entries)


@wiki_bp.route('/tag/<slug>')
@login_required
def tag(slug):
    tag = Tag.query.filter_by(slug=slug).first_or_404()
    readable_ids = [s.id for s in current_user.readable_spaces()]
    pages = sorted(
        [p for p in tag.pages if p.space_id in readable_ids],
        key=lambda p: p.title.lower()
    )
    return render_template('wiki/tag.html', tag=tag, pages=pages, excerpt=excerpt)


@wiki_bp.route('/space/<space_slug>/<page_slug>/print')
@login_required
def print_page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    return render_template('wiki/print.html', space=space, page=page,
                           body_html=render_markdown(page.content))


def _pdf_link_callback(uri, rel):
    """Loest /uploads/... und statische URLs zu lokalen Dateipfaden auf (fuer Bilder im PDF)."""
    try:
        if uri.startswith('/uploads/'):
            return os.path.join(current_app.config['UPLOAD_DIR'], uri.split('/uploads/', 1)[1])
        if uri.startswith('/static/'):
            return os.path.join(current_app.root_path, 'static', uri.split('/static/', 1)[1])
    except Exception:
        pass
    return uri


@wiki_bp.route('/space/<space_slug>/<page_slug>/pdf')
@login_required
def pdf_page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    from xhtml2pdf import pisa
    html = render_template('wiki/pdf.html', space=space, page=page,
                           body_html=render_markdown(page.content),
                           wiki_name=current_app.config.get('WIKI_NAME', 'Wiki'))
    buf = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=buf, encoding='utf-8',
                   link_callback=_pdf_link_callback)
    buf.seek(0)
    filename = (page.slug or 'seite') + '.pdf'
    return Response(buf.read(), mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'})


@wiki_bp.route('/search')
@login_required
def search():
    q = (request.args.get('q') or '').strip()
    results = []
    if q:
        readable_ids = [s.id for s in current_user.readable_spaces()]
        if readable_ids:
            like = f'%{q}%'
            results = (
                Page.query.filter(
                    Page.space_id.in_(readable_ids),
                    or_(
                        Page.title.ilike(like),
                        Page.content.ilike(like),
                        Page.tags.any(Tag.name.ilike(like)),
                    ),
                )
                .order_by(Page.updated_at.desc())
                .limit(50)
                .all()
            )
    return render_template('wiki/search.html', q=q, results=results, highlight=highlight)


# -- Favoriten ---------------------------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>/favorite', methods=['POST'])
@login_required
def toggle_favorite(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_read(space)
    page = _get_page_or_404(space, page_slug)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    fav = Favorite.query.filter_by(user_id=current_user.id, page_id=page.id).first()
    if fav:
        db.session.delete(fav)
        added = False
    else:
        db.session.add(Favorite(user_id=current_user.id, page_id=page.id))
        added = True
    db.session.commit()
    if request.accept_mimetypes.best == 'application/json' or request.args.get('ajax'):
        return jsonify(favorite=added)
    return redirect(url_for('wiki.page', space_slug=space.slug, page_slug=page.slug))


# -- Schnellsuche (Command-Palette, Strg+K) ----------------------------------

@wiki_bp.route('/api/quickfind')
@login_required
def quickfind():
    q = (request.args.get('q') or '').strip()
    items = []
    if q:
        readable_ids = [s.id for s in current_user.readable_spaces()]
        if readable_ids:
            like = f'%{q}%'
            pages = (
                Page.query.filter(
                    Page.space_id.in_(readable_ids),
                    or_(Page.title.ilike(like), Page.tags.any(Tag.name.ilike(like))),
                )
                .order_by(Page.updated_at.desc())
                .limit(20)
                .all()
            )
            for p in pages:
                items.append({
                    'title': p.title,
                    'space': p.space.name,
                    'url': url_for('wiki.page', space_slug=p.space.slug, page_slug=p.slug),
                })
    return jsonify(results=items)


# -- Seiten verschieben & sortieren ------------------------------------------

@wiki_bp.route('/space/<space_slug>/<page_slug>/move', methods=['GET', 'POST'])
@login_required
def move_page(space_slug, page_slug):
    space = _get_space_or_404(space_slug)
    require_write(space)
    page = _get_page_or_404(space, page_slug)

    # Ziel-Bereiche: nur solche, in denen der Nutzer schreiben darf (eingerueckt)
    all_spaces = Space.query.order_by(Space.position, Space.name).all()
    by_parent = {}
    for s in all_spaces:
        by_parent.setdefault(s.parent_id, []).append(s)
    target_choices = []

    def walk(pid, depth):
        for s in by_parent.get(pid, []):
            if current_user.can_write(s):
                target_choices.append((s.id, ('   ' * depth) + ('↳ ' if depth else '') + s.name))
            walk(s.id, depth + 1)
    walk(None, 0)

    form = MovePageForm()
    form.target_space.choices = target_choices

    if request.method == 'POST':
        target_id = form.target_space.data
    else:
        try:
            target_id = int(request.args.get('target', space.id))
        except (TypeError, ValueError):
            target_id = space.id
        form.target_space.data = target_id
    target = db.session.get(Space, target_id) if target_id else None
    if target is None or not current_user.can_write(target):
        target = space
        form.target_space.data = space.id
    exclude = page if target.id == page.space_id else None
    form.parent_id.choices = _parent_choices(target, exclude=exclude)
    if request.method == 'GET':
        form.parent_id.data = page.parent_id if (target.id == page.space_id and page.parent_id) else 0

    if form.validate_on_submit():
        target = db.session.get(Space, form.target_space.data)
        if target is None or not current_user.can_write(target):
            abort(403)
        new_parent = form.parent_id.data or None
        if new_parent:
            pp = db.session.get(Page, new_parent)
            if (pp is None or pp.space_id != target.id or new_parent == page.id
                    or new_parent in page.descendant_ids()):
                new_parent = None
        _move_page_subtree(page, target, new_parent)
        db.session.commit()
        flash('Seite wurde verschoben.', 'success')
        return redirect(url_for('wiki.page', space_slug=target.slug, page_slug=page.slug))
    return render_template('wiki/move.html', space=space, page=page, form=form, target=target)


@wiki_bp.route('/space/<space_slug>/<page_slug>/reorder/<direction>', methods=['POST'])
@login_required
def reorder_page(space_slug, page_slug, direction):
    space = _get_space_or_404(space_slug)
    require_write(space)
    page = _get_page_or_404(space, page_slug)
    if direction not in ('up', 'down'):
        abort(400)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    _reorder(Page, page, direction, space_id=page.space_id, parent_id=page.parent_id)
    db.session.commit()
    return redirect(request.referrer or url_for('wiki.space', space_slug=space.slug))


@wiki_bp.route('/api/move', methods=['POST'])
@login_required
def api_move():
    """Drag & Drop: ein Element unter ein Ziel haengen (verschieben/umhaengen)."""
    data = request.get_json(silent=True) or {}
    kind = data.get('kind')
    item_id = data.get('id')
    ref_kind = data.get('ref_kind')
    ref_id = data.get('ref_id')

    if kind == 'page':
        page = db.session.get(Page, item_id)
        if page is None:
            return jsonify(error='Seite nicht gefunden'), 404
        if not current_user.can_write(page.space):
            return jsonify(error='Keine Schreibrechte'), 403
        if ref_kind == 'page':
            ref = db.session.get(Page, ref_id)
            if ref is None:
                return jsonify(error='Ziel nicht gefunden'), 400
            if ref.id == page.id or ref.id in page.descendant_ids():
                return jsonify(error='Ungueltiges Ziel (Zyklus)'), 400
            target_space = ref.space
            new_parent = ref.id
        elif ref_kind == 'space':
            target_space = db.session.get(Space, ref_id)
            if target_space is None:
                return jsonify(error='Ziel-Bereich nicht gefunden'), 400
            new_parent = None
        else:
            return jsonify(error='Ungueltiges Ziel'), 400
        if not current_user.can_write(target_space):
            return jsonify(error='Keine Schreibrechte im Ziel-Bereich'), 403
        _move_page_subtree(page, target_space, new_parent)
        db.session.commit()
        return jsonify(ok=True)

    if kind == 'space':
        if not current_user.is_admin:
            return jsonify(error='Nur Admins duerfen Bereiche verschieben'), 403
        sp = db.session.get(Space, item_id)
        if sp is None:
            return jsonify(error='Bereich nicht gefunden'), 404
        if ref_kind == 'space':
            ref = db.session.get(Space, ref_id)
            if ref is None:
                return jsonify(error='Ziel nicht gefunden'), 400
            if ref.id == sp.id or ref.id in sp.descendant_ids():
                return jsonify(error='Ungueltiges Ziel (Zyklus)'), 400
            sp.parent_id = ref.id
        elif ref_kind == 'root':
            sp.parent_id = None
        else:
            return jsonify(error='Ungueltiges Ziel'), 400
        sp.position = _next_space_position(sp.parent_id)
        db.session.commit()
        return jsonify(ok=True)

    return jsonify(error='Unbekannter Typ'), 400
