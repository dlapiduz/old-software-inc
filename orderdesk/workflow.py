# -*- coding: utf-8 -*-
"""
Order lifecycle.

    draft -> submitted -> approved -> shipped -> invoiced
      \           \           \
       +-----------+-----------+--> cancelled

Submitting reserves stock, shipping takes it out of stock, cancelling
gives reservations back.
"""
from datetime import datetime

import audit
import inventory
import notifications
from extensions import db
from models import Order, OrderLine, PromoCode

TRANSITIONS = {
    'draft': ('submitted', 'cancelled'),
    'submitted': ('approved', 'cancelled'),
    'approved': ('shipped', 'cancelled'),
    'shipped': ('invoiced',),
    'invoiced': (),
    'cancelled': (),
}

ACTION_FOR_STATUS = {
    'submitted': 'submit',
    'approved': 'approve',
    'shipped': 'ship',
    'invoiced': 'invoice',
    'cancelled': 'cancel',
}


class WorkflowError(Exception):
    pass


def _require(order, target):
    if target not in TRANSITIONS.get(order.status, ()):
        raise WorkflowError('Cannot move order %s from %s to %s'
                            % (order.number, order.status, target))


def _audit(order, user, action, detail=None):
    audit.record(user, action, 'order', order.id, detail)


def _notify(order, event):
    notifications.notify('order.%s' % event, {
        'number': order.number,
        'status': order.status,
        'customer': order.customer.account_number,
        'total_cents': order.total_cents,
    })


def create_order(customer, user, notes=None):
    order = Order(customer=customer, number=Order.next_number(), status='draft',
                  notes=notes, created_by_id=getattr(user, 'id', None))
    db.session.add(order)
    db.session.flush()
    _audit(order, user, 'create')
    return order


def add_line(order, product, quantity, user=None):
    if not order.is_editable:
        raise WorkflowError('Order %s is %s and can no longer be edited'
                            % (order.number, order.status))
    if quantity is None or quantity <= 0:
        raise WorkflowError('Quantity must be a positive number')
    if product.discontinued:
        raise WorkflowError('Product %s is discontinued' % product.sku)

    for line in order.lines:
        if line.product is product:
            line.quantity += quantity
            break
    else:
        line = OrderLine(product=product, quantity=quantity,
                         unit_price_cents=product.price_cents)
        order.lines.append(line)

    order.recalculate()
    _audit(order, user, 'add_line', u'%d x %s' % (quantity, product.sku))
    return line


def remove_line(order, line_id, user=None):
    if not order.is_editable:
        raise WorkflowError('Order %s is %s and can no longer be edited'
                            % (order.number, order.status))
    matches = [l for l in order.lines if l.id == line_id]
    if not matches:
        raise WorkflowError('Line %s is not on order %s' % (line_id, order.number))
    line = matches[0]
    order.lines.remove(line)
    order.recalculate()
    _audit(order, user, 'remove_line', u'%d x %s' % (line.quantity, line.product.sku))


def apply_promo(order, code, user=None):
    if not order.is_editable:
        raise WorkflowError('Order %s is %s and can no longer be edited'
                            % (order.number, order.status))
    code = (code or '').strip().upper()
    if not code:
        order.promo_code = None
        order.recalculate()
        _audit(order, user, 'clear_promo')
        return None

    order.recalculate()
    promo = PromoCode.query.filter_by(code=code).first()
    if promo is None or not promo.is_valid(order.subtotal - order.line_discount):
        raise WorkflowError('Promo code %s is not valid for this order' % code)
    order.promo_code = code
    order.recalculate()
    _audit(order, user, 'apply_promo', unicode(code))
    return promo


def submit_order(order, user):
    _require(order, 'submitted')
    if not order.lines:
        raise WorkflowError('Cannot submit an order with no lines')

    order.recalculate()
    customer = order.customer
    if customer.credit_limit_cents:
        exposure = customer.open_balance() + order.total
        if exposure > customer.credit_limit:
            raise WorkflowError('Credit limit exceeded for %s: limit %s, exposure %s'
                                % (customer.account_number, customer.credit_limit, exposure))

    reserved = []
    try:
        for line in order.lines:
            inventory.reserve(line.product, line.quantity)
            reserved.append(line)
    except inventory.InsufficientStock, e:
        for line in reserved:
            inventory.release(line.product, line.quantity)
        raise WorkflowError(str(e))

    order.status = 'submitted'
    order.submitted_at = datetime.utcnow()
    _audit(order, user, 'submit')
    _notify(order, 'submitted')
    return order


def approve_order(order, user):
    _require(order, 'approved')
    if user is None or getattr(user, 'role', None) != 'admin':
        raise WorkflowError('Only administrators can approve orders')
    order.status = 'approved'
    _audit(order, user, 'approve')
    _notify(order, 'approved')
    return order


def ship_order(order, user):
    _require(order, 'shipped')
    for line in order.lines:
        inventory.commit(line.product, line.quantity)
    order.status = 'shipped'
    order.shipped_at = datetime.utcnow()
    _audit(order, user, 'ship')
    _notify(order, 'shipped')
    return order


def invoice_order(order, user):
    _require(order, 'invoiced')
    order.status = 'invoiced'
    order.invoiced_at = datetime.utcnow()
    _audit(order, user, 'invoice')
    _notify(order, 'invoiced')
    return order


def cancel_order(order, user, reason=None):
    _require(order, 'cancelled')
    if order.status == 'submitted':
        for line in order.lines:
            inventory.release(line.product, line.quantity)
    order.status = 'cancelled'
    _audit(order, user, 'cancel', reason)
    _notify(order, 'cancelled')
    return order


ACTIONS = {
    'submit': submit_order,
    'approve': approve_order,
    'ship': ship_order,
    'invoice': invoice_order,
    'cancel': cancel_order,
}
