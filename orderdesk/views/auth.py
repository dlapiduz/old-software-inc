from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask.ext.login import current_user, login_required, login_user, logout_user

from orderdesk import audit
from orderdesk.extensions import db
from orderdesk.forms import LoginForm
from orderdesk.models import User
from orderdesk.security import check_password

bp = Blueprint('auth', __name__)


@bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data.strip()).first()
        if user is not None and user.is_active() and \
                check_password(user.password_hash, form.password.data):
            login_user(user, remember=form.remember.data)
            audit.record(user, 'login', 'user', user.id)
            db.session.commit()
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        flash(u'Invalid username or password.', 'error')
    return render_template('auth/login.html', form=form)


@bp.route('/logout')
@login_required
def logout():
    audit.record(current_user, 'logout', 'user', current_user.id)
    db.session.commit()
    logout_user()
    flash(u'You have been logged out.', 'info')
    return redirect(url_for('.login'))
