from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask.ext.login import current_user, login_required

from orderdesk import workflow
from orderdesk.decorators import editor_required
from orderdesk.extensions import db
from orderdesk.forms import NewOrderForm, OrderLineForm, PromoForm
from orderdesk.models import ORDER_STATUSES, AuditEntry, Customer, Order, Product
from orderdesk.utils import paginate

bp = Blueprint('orders', __name__)


def _get_order(number):
    order = Order.query.filter_by(number=number).first()
    if order is None:
        abort(404)
    return order


def _product_choices():
    products = Product.query.filter_by(discontinued=False).order_by(Product.sku).all()
    return [(p.id, u'%s - %s (%s)' % (p.sku, p.name, p.price)) for p in products]


@bp.route('/orders')
@login_required
def index():
    status = request.args.get('status')
    query = Order.query
    if status in ORDER_STATUSES:
        query = query.filter_by(status=status)
    page = paginate(query.order_by(Order.created_at.desc()), request.args.get('page', 1, type=int))
    return render_template('orders/index.html', page=page, status=status,
                           statuses=ORDER_STATUSES)


@bp.route('/orders/new', methods=['GET', 'POST'])
@editor_required
def create():
    form = NewOrderForm()
    form.customer_id.choices = [(c.id, u'%s - %s' % (c.account_number, c.name))
                                for c in Customer.query.order_by(Customer.name)]
    if request.method == 'GET' and request.args.get('customer_id'):
        form.customer_id.data = request.args.get('customer_id', type=int)
    if form.validate_on_submit():
        customer = Customer.query.get_or_404(form.customer_id.data)
        order = workflow.create_order(customer, current_user, notes=form.notes.data or None)
        db.session.commit()
        flash(u'Draft order %s created.' % order.number, 'success')
        return redirect(url_for('.detail', number=order.number))
    return render_template('orders/new.html', form=form)


@bp.route('/orders/<number>')
@login_required
def detail(number):
    order = _get_order(number)
    line_form = OrderLineForm()
    line_form.product_id.choices = _product_choices()
    promo_form = PromoForm(code=order.promo_code)
    history = AuditEntry.query.filter_by(object_type='order', object_id=order.id) \
        .order_by(AuditEntry.created_at, AuditEntry.id).all()
    return render_template('orders/detail.html', order=order, line_form=line_form,
                           promo_form=promo_form, history=history)


@bp.route('/orders/<number>/lines', methods=['POST'])
@editor_required
def add_line(number):
    order = _get_order(number)
    form = OrderLineForm()
    form.product_id.choices = _product_choices()
    if form.validate_on_submit():
        product = Product.query.get_or_404(form.product_id.data)
        try:
            workflow.add_line(order, product, form.quantity.data, current_user)
            db.session.commit()
            flash(u'Added %d x %s.' % (form.quantity.data, product.sku), 'success')
        except workflow.WorkflowError, e:
            db.session.rollback()
            flash(unicode(e), 'error')
    else:
        for field, errors in form.errors.iteritems():
            for error in errors:
                flash(u'%s: %s' % (getattr(form, field).label.text, error), 'error')
    return redirect(url_for('.detail', number=number))


@bp.route('/orders/<number>/lines/<int:line_id>/delete', methods=['POST'])
@editor_required
def remove_line(number, line_id):
    order = _get_order(number)
    try:
        workflow.remove_line(order, line_id, current_user)
        db.session.commit()
        flash(u'Line removed.', 'success')
    except workflow.WorkflowError, e:
        db.session.rollback()
        flash(unicode(e), 'error')
    return redirect(url_for('.detail', number=number))


@bp.route('/orders/<number>/promo', methods=['POST'])
@editor_required
def apply_promo(number):
    order = _get_order(number)
    form = PromoForm()
    if form.validate_on_submit():
        try:
            promo = workflow.apply_promo(order, form.code.data, current_user)
            db.session.commit()
            if promo is None:
                flash(u'Promo code removed.', 'info')
            else:
                flash(u'Promo code %s applied.' % promo.code, 'success')
        except workflow.WorkflowError, e:
            db.session.rollback()
            flash(unicode(e), 'error')
    return redirect(url_for('.detail', number=number))


@bp.route('/orders/<number>/transition/<action>', methods=['POST'])
@editor_required
def transition(number, action):
    if not workflow.ACTIONS.has_key(action):
        abort(404)
    order = _get_order(number)
    try:
        workflow.ACTIONS[action](order, current_user)
        db.session.commit()
        flash(u'Order %s is now %s.' % (order.number, order.status), 'success')
    except workflow.WorkflowError, e:
        db.session.rollback()
        flash(unicode(e), 'error')
    return redirect(url_for('.detail', number=number))
