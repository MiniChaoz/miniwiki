from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user

from ..extensions import db
from ..forms import ChangePasswordForm

profile_bp = Blueprint('profile', __name__)


@profile_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Das aktuelle Passwort ist falsch.', 'danger')
        else:
            current_user.set_password(form.password.data)
            db.session.commit()
            flash('Passwort wurde geaendert.', 'success')
            return redirect(url_for('profile.profile'))
    return render_template('profile.html', form=form)
