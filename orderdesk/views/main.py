from flask import Blueprint, render_template
from flask.ext.login import login_required

from orderdesk.extensions import db
from orderdesk.inventory import low_stock_products
from orderdesk.models import ORDER_STATUSES, Order

bp = Blueprint('main', __name__)


@bp.route('/')
@login_required
def dashboard():
    counts = dict((s, 0) for s in ORDER_STATUSES)
    rows = db.session.query(Order.status, db.func.count(Order.id)).group_by(Order.status).all()
    for status, n in rows:
        counts[status] = n
    recent = Order.query.order_by(Order.created_at.desc()).limit(10).all()
    return render_template('dashboard.html', counts=counts, statuses=ORDER_STATUSES,
                           recent=recent, low_stock=low_stock_products())
