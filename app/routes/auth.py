from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse

from ..extensions import db
from ..models import User
from ..forms import LoginForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('wiki.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is None or not user.check_password(form.password.data):
            flash('Benutzername oder Passwort ist falsch.', 'danger')
        elif not user.is_active:
            flash('Dieses Konto ist deaktiviert.', 'danger')
        else:
            login_user(user, remember=form.remember.data)
            db.session.commit()
            nxt = request.args.get('next')
            # Nur lokale Weiterleitungen zulassen (Open-Redirect-Schutz)
            if not nxt or urlparse(nxt).netloc:
                nxt = url_for('wiki.index')
            return redirect(nxt)
    return render_template('auth/login.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Du wurdest abgemeldet.', 'info')
    return redirect(url_for('auth.login'))
