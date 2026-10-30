from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask.ext.login import current_user, login_required

from orderdesk import audit
from orderdesk.decorators import editor_required
from orderdesk.extensions import db
from orderdesk.forms import CustomerForm
from orderdesk.models import Customer, Order
from orderdesk.utils import paginate

bp = Blueprint('customers', __name__)


def _apply_form(form, customer):
    customer.name = form.name.data.strip()
    customer.email = form.email.data or None
    customer.phone = form.phone.data or None
    customer.tier = form.tier.data
    customer.tax_exempt = form.tax_exempt.data
    customer.credit_limit = form.credit_limit_amount.data or 0
    customer.notes = form.notes.data or None


@bp.route('/customers')
@login_required
def index():
    q = request.args.get('q', u'').strip()
    query = Customer.query
    if q:
        like = u'%' + q + u'%'
        query = query.filter(db.or_(Customer.name.like(like),
                                    Customer.account_number.like(like),
                                    Customer.email.like(like)))
    page = paginate(query.order_by(Customer.name), request.args.get('page', 1, type=int))
    return render_template('customers/index.html', page=page, q=q)


@bp.route('/customers/new', methods=['GET', 'POST'])
@editor_required
def create():
    form = CustomerForm()
    if form.validate_on_submit():
        customer = Customer(account_number=Customer.next_account_number())
        _apply_form(form, customer)
        db.session.add(customer)
        db.session.flush()
        audit.record(current_user, 'create', 'customer', customer.id, customer.name)
        db.session.commit()
        flash(u'Customer %s created.' % customer.account_number, 'success')
        return redirect(url_for('.detail', customer_id=customer.id))
    return render_template('customers/form.html', form=form, customer=None)


@bp.route('/customers/<int:customer_id>')
@login_required
def detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    orders = customer.orders.order_by(Order.created_at.desc()).limit(25).all()
    return render_template('customers/detail.html', customer=customer, orders=orders)


@bp.route('/customers/<int:customer_id>/edit', methods=['GET', 'POST'])
@editor_required
def edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    form = CustomerForm(obj=customer)
    if request.method == 'GET' and customer.credit_limit_cents:
        form.credit_limit_amount.data = customer.credit_limit.as_decimal()
    if form.validate_on_submit():
        _apply_form(form, customer)
        audit.record(current_user, 'update', 'customer', customer.id)
        db.session.commit()
        flash(u'Customer %s updated.' % customer.account_number, 'success')
        return redirect(url_for('.detail', customer_id=customer.id))
    return render_template('customers/form.html', form=form, customer=customer)
