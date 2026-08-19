from flask import (
    Blueprint, render_template, redirect, url_for, flash, request, abort,
)
from flask_login import current_user

from ..extensions import db
from ..models import (
    User, Space, SpaceMembership, Page, PageTemplate,
    ROLE_ADMIN, ACCESS_LABELS,
)
from ..forms import UserForm, SpaceForm, MembershipForm, ConfirmForm, PageTemplateForm
from ..permissions import admin_required
from ..textutils import slugify

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def _space_parent_choices(exclude=None):
    """Auswahlliste moeglicher Elternbereiche (eingerueckt), ohne den Bereich
    selbst und seine Unterbereiche (verhindert Zyklen)."""
    blocked = set()
    if exclude is not None:
        blocked = set(exclude.descendant_ids()) | {exclude.id}
    spaces = Space.query.order_by(Space.position, Space.name).all()
    by_parent = {}
    for s in spaces:
        by_parent.setdefault(s.parent_id, []).append(s)
    choices = [(0, '— keine (oberste Ebene) —')]

    def walk(parent_id, depth):
        for s in by_parent.get(parent_id, []):
            if s.id in blocked:
                continue
            choices.append((s.id, ('   ' * depth) + '↳ ' + s.name if depth else s.name))
            walk(s.id, depth + 1)

    walk(None, 0)
    return choices


def _ordered_spaces():
    """Alle Bereiche als [(space, tiefe), ...] in Baum-Reihenfolge (fuer Admin-Liste)."""
    spaces = Space.query.order_by(Space.position, Space.name).all()
    by_parent = {}
    for s in spaces:
        by_parent.setdefault(s.parent_id, []).append(s)
    ordered = []

    def walk(parent_id, depth):
        for s in sorted(by_parent.get(parent_id, []), key=lambda x: (x.position, x.name.lower())):
            ordered.append((s, depth))
            walk(s.id, depth + 1)

    walk(None, 0)
    return ordered


# -- Nutzer ------------------------------------------------------------------

@admin_bp.route('/users')
@admin_required
def users():
    all_users = User.query.order_by(User.username).all()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new_user():
    form = UserForm(require_password=True)
    if form.validate_on_submit():
        uname = form.username.data.strip()
        if User.query.filter_by(username=uname).first():
            flash('Dieser Benutzername ist bereits vergeben.', 'danger')
        else:
            user = User(
                username=uname,
                display_name=form.display_name.data or uname,
                email=form.email.data or None,
                role=form.role.data,
                is_active=form.is_active.data,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash('Nutzer wurde angelegt.', 'success')
            return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', form=form, user=None)


@admin_bp.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        uname = form.username.data.strip()
        clash = User.query.filter(User.username == uname, User.id != user.id).first()
        if clash:
            flash('Dieser Benutzername ist bereits vergeben.', 'danger')
        else:
            # Schutz: sich selbst nicht die Admin-Rolle/Deaktivierung entziehen
            if user.id == current_user.id and (form.role.data != ROLE_ADMIN or not form.is_active.data):
                flash('Du kannst dir nicht selbst die Admin-Rechte oder die Aktivierung entziehen.', 'warning')
            else:
                user.username = uname
                user.display_name = form.display_name.data or uname
                user.email = form.email.data or None
                user.role = form.role.data
                user.is_active = form.is_active.data
                if form.password.data:
                    user.set_password(form.password.data)
                db.session.commit()
                flash('Nutzer wurde gespeichert.', 'success')
                return redirect(url_for('admin.users'))
    return render_template('admin/user_form.html', form=form, user=user)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id) or abort(404)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    if user.id == current_user.id:
        flash('Du kannst dich nicht selbst loeschen.', 'warning')
        return redirect(url_for('admin.users'))
    db.session.delete(user)
    db.session.commit()
    flash('Nutzer wurde geloescht.', 'info')
    return redirect(url_for('admin.users'))


# -- Bereiche ----------------------------------------------------------------

@admin_bp.route('/spaces')
@admin_required
def spaces():
    ordered = _ordered_spaces()
    counts = {s.id: Page.query.filter_by(space_id=s.id).count() for s, _ in ordered}
    return render_template('admin/spaces.html', ordered=ordered, counts=counts)


@admin_bp.route('/spaces/new', methods=['GET', 'POST'])
@admin_required
def new_space():
    form = SpaceForm()
    form.parent_id.choices = _space_parent_choices()
    if request.method == 'GET':
        # Vorbelegung, wenn als Unterbereich angelegt (?parent=id)
        pid = request.args.get('parent')
        if pid and pid.isdigit():
            parent = db.session.get(Space, int(pid))
            if parent:
                form.parent_id.data = parent.id
                form.default_access.data = parent.default_access  # bequeme Vorbelegung
    if form.validate_on_submit():
        slug = slugify(form.slug.data or form.name.data)
        if Space.query.filter_by(slug=slug).first():
            flash('Dieser Kurzname ist bereits vergeben.', 'danger')
        else:
            parent_id = form.parent_id.data or None
            if parent_id and not db.session.get(Space, parent_id):
                parent_id = None
            space = Space(
                slug=slug,
                name=form.name.data.strip(),
                description=form.description.data or None,
                parent_id=parent_id,
                default_access=form.default_access.data,
            )
            db.session.add(space)
            db.session.commit()
            flash('Bereich wurde angelegt.', 'success')
            return redirect(url_for('admin.space_members', space_id=space.id))
    return render_template('admin/space_form.html', form=form, space=None)


@admin_bp.route('/spaces/<int:space_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_space(space_id):
    space = db.session.get(Space, space_id) or abort(404)
    form = SpaceForm(obj=space)
    form.parent_id.choices = _space_parent_choices(exclude=space)
    if request.method == 'GET':
        form.parent_id.data = space.parent_id or 0
    if form.validate_on_submit():
        slug = slugify(form.slug.data or form.name.data)
        clash = Space.query.filter(Space.slug == slug, Space.id != space.id).first()
        if clash:
            flash('Dieser Kurzname ist bereits vergeben.', 'danger')
        else:
            new_parent = form.parent_id.data or None
            # Ungueltige/zyklische Elternwahl abfangen
            if new_parent and (new_parent == space.id or new_parent in space.descendant_ids()
                               or not db.session.get(Space, new_parent)):
                new_parent = space.parent_id
            space.slug = slug
            space.name = form.name.data.strip()
            space.description = form.description.data or None
            space.parent_id = new_parent
            space.default_access = form.default_access.data
            db.session.commit()
            flash('Bereich wurde gespeichert.', 'success')
            return redirect(url_for('admin.spaces'))
    return render_template('admin/space_form.html', form=form, space=space)


@admin_bp.route('/spaces/<int:space_id>/delete', methods=['POST'])
@admin_required
def delete_space(space_id):
    space = db.session.get(Space, space_id) or abort(404)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    db.session.delete(space)
    db.session.commit()
    flash('Bereich (samt Seiten) wurde geloescht.', 'info')
    return redirect(url_for('admin.spaces'))


@admin_bp.route('/spaces/<int:space_id>/reorder/<direction>', methods=['POST'])
@admin_required
def reorder_space(space_id, direction):
    sp = db.session.get(Space, space_id) or abort(404)
    if direction not in ('up', 'down'):
        abort(400)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    sibs = (Space.query.filter_by(parent_id=sp.parent_id)
            .order_by(Space.position, Space.name).all())
    for i, s in enumerate(sibs):
        s.position = i
    idx = next((i for i, s in enumerate(sibs) if s.id == sp.id), None)
    if idx is not None:
        j = idx - 1 if direction == 'up' else idx + 1
        if 0 <= j < len(sibs):
            sibs[idx].position, sibs[j].position = sibs[j].position, sibs[idx].position
    db.session.commit()
    return redirect(url_for('admin.spaces'))


# -- Mitgliedschaften pro Bereich -------------------------------------------

@admin_bp.route('/spaces/<int:space_id>/members', methods=['GET', 'POST'])
@admin_required
def space_members(space_id):
    space = db.session.get(Space, space_id) or abort(404)
    existing_ids = {m.user_id for m in space.memberships}
    candidates = (
        User.query.filter(~User.id.in_(existing_ids) if existing_ids else True)
        .order_by(User.username)
        .all()
    )
    form = MembershipForm()
    form.user_id.choices = [(u.id, f'{u.name} ({u.username})') for u in candidates]

    if form.validate_on_submit():
        if not candidates:
            flash('Alle Nutzer sind bereits Mitglied.', 'warning')
        else:
            existing = SpaceMembership.query.filter_by(
                space_id=space.id, user_id=form.user_id.data
            ).first()
            if existing:
                existing.access = form.access.data
            else:
                db.session.add(SpaceMembership(
                    space_id=space.id, user_id=form.user_id.data, access=form.access.data,
                ))
            db.session.commit()
            flash('Zugriff wurde gesetzt.', 'success')
            return redirect(url_for('admin.space_members', space_id=space.id))

    return render_template(
        'admin/space_members.html',
        space=space, form=form,
        members=space.memberships,
        access_labels=ACCESS_LABELS,
        has_candidates=bool(candidates),
    )


# -- Seiten-Vorlagen ---------------------------------------------------------

@admin_bp.route('/templates')
@admin_required
def templates():
    tpls = PageTemplate.query.order_by(PageTemplate.name).all()
    return render_template('admin/templates.html', templates=tpls)


@admin_bp.route('/templates/new', methods=['GET', 'POST'])
@admin_required
def new_template():
    form = PageTemplateForm()
    if form.validate_on_submit():
        db.session.add(PageTemplate(
            name=form.name.data.strip(),
            description=form.description.data or None,
            title_hint=form.title_hint.data or None,
            content=form.content.data or '',
        ))
        db.session.commit()
        flash('Vorlage wurde angelegt.', 'success')
        return redirect(url_for('admin.templates'))
    return render_template('admin/template_form.html', form=form, tpl=None)


@admin_bp.route('/templates/<int:tpl_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit_template(tpl_id):
    tpl = db.session.get(PageTemplate, tpl_id) or abort(404)
    form = PageTemplateForm(obj=tpl)
    if form.validate_on_submit():
        tpl.name = form.name.data.strip()
        tpl.description = form.description.data or None
        tpl.title_hint = form.title_hint.data or None
        tpl.content = form.content.data or ''
        db.session.commit()
        flash('Vorlage wurde gespeichert.', 'success')
        return redirect(url_for('admin.templates'))
    return render_template('admin/template_form.html', form=form, tpl=tpl)


@admin_bp.route('/templates/<int:tpl_id>/delete', methods=['POST'])
@admin_required
def delete_template(tpl_id):
    tpl = db.session.get(PageTemplate, tpl_id) or abort(404)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    db.session.delete(tpl)
    db.session.commit()
    flash('Vorlage wurde geloescht.', 'info')
    return redirect(url_for('admin.templates'))


@admin_bp.route('/spaces/<int:space_id>/members/<int:membership_id>/delete', methods=['POST'])
@admin_required
def remove_member(space_id, membership_id):
    space = db.session.get(Space, space_id) or abort(404)
    m = db.session.get(SpaceMembership, membership_id)
    if m is None or m.space_id != space.id:
        abort(404)
    form = ConfirmForm()
    if not form.validate_on_submit():
        abort(400)
    db.session.delete(m)
    db.session.commit()
    flash('Zugriff wurde entfernt.', 'info')
    return redirect(url_for('admin.space_members', space_id=space.id))
