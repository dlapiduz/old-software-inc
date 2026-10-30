"""
JSON API, v1. Used by the WMS and the EDI bridge.

Authenticate with the ``X-OrderDesk-Token`` header (or ``?token=``).
"""
from functools import wraps

from flask import Blueprint, g, jsonify, request

from orderdesk import workflow
from orderdesk.extensions import db
from orderdesk.models import ORDER_STATUSES, Customer, Order, Product, User

bp = Blueprint('api', __name__)


def _error(message, status):
    resp = jsonify(error=message)
    resp.status_code = status
    return resp


def token_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        token = request.headers.get('X-OrderDesk-Token') or request.args.get('token')
        user = None
        if token:
            user = User.query.filter_by(api_token=token, active=True).first()
        if user is None:
            return _error('invalid or missing API token', 401)
        g.api_user = user
        return f(*args, **kwargs)
    return wrapped


@bp.route('/products')
@token_required
def list_products():
    query = Product.query
    if request.args.get('include_discontinued') != '1':
        query = query.filter_by(discontinued=False)
    return jsonify(products=[p.to_dict() for p in query.order_by(Product.sku)])


@bp.route('/products/<sku>')
@token_required
def get_product(sku):
    product = Product.query.filter_by(sku=sku.upper()).first()
    if product is None:
        return _error('no such product', 404)
    return jsonify(product=product.to_dict())


@bp.route('/orders')
@token_required
def list_orders():
    query = Order.query
    status = request.args.get('status')
    if status:
        if status not in ORDER_STATUSES:
            return _error('unknown status %s' % status, 400)
        query = query.filter_by(status=status)
    limit = request.args.get('limit', 50, type=int)
    orders = query.order_by(Order.created_at.desc()).limit(limit).all()
    return jsonify(orders=[o.to_dict(include_lines=False) for o in orders])


@bp.route('/orders/<number>')
@token_required
def get_order(number):
    order = Order.query.filter_by(number=number).first()
    if order is None:
        return _error('no such order', 404)
    return jsonify(order=order.to_dict())


@bp.route('/orders', methods=['POST'])
@token_required
def create_order():
    data = request.json
    if not isinstance(data, dict):
        return _error('expected a JSON object', 400)
    customer = Customer.query.filter_by(account_number=data.get('customer')).first()
    if customer is None:
        return _error('unknown customer %s' % data.get('customer'), 400)
    lines = data.get('lines')
    if not isinstance(lines, list) or not lines:
        return _error('an order needs at least one line', 400)

    try:
        order = workflow.create_order(customer, g.api_user, notes=data.get('notes'))
        for item in lines:
            product = Product.query.filter_by(sku=item.get('sku')).first()
            if product is None:
                raise workflow.WorkflowError('unknown sku %s' % item.get('sku'))
            workflow.add_line(order, product, int(item.get('quantity', 0)), g.api_user)
        if data.get('promo_code'):
            workflow.apply_promo(order, data['promo_code'], g.api_user)
        if data.get('submit'):
            workflow.submit_order(order, g.api_user)
        db.session.commit()
    except (workflow.WorkflowError, ValueError), e:
        db.session.rollback()
        return _error(e.message, 422)

    resp = jsonify(order=order.to_dict())
    resp.status_code = 201
    return resp


@bp.route('/orders/<number>/<action>', methods=['POST'])
@token_required
def order_action(number, action):
    if not workflow.ACTIONS.has_key(action):
        return _error('unknown action %s' % action, 404)
    order = Order.query.filter_by(number=number).first()
    if order is None:
        return _error('no such order', 404)
    try:
        workflow.ACTIONS[action](order, g.api_user)
        db.session.commit()
    except workflow.WorkflowError, e:
        db.session.rollback()
        return _error(e.message, 422)
    return jsonify(order=order.to_dict())
