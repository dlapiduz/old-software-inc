# -*- coding: utf-8 -*-
from orderdesk import workflow
from orderdesk.extensions import db
from orderdesk.models import Customer, Product, PromoCode, User
from orderdesk.security import hash_password

_seq = [0]


def _next():
    _seq[0] += 1
    return _seq[0]


def make_user(username=None, password='secret', role='clerk', **kwargs):
    n = _next()
    user = User(username=username or 'user%d' % n, email='user%d@example.com' % n,
                role=role, password_hash=hash_password(password),
                api_token='token-%d' % n, **kwargs)
    db.session.add(user)
    db.session.flush()
    return user


def make_customer(name=None, tier='standard', tax_exempt=False, credit_limit_cents=0, **kwargs):
    n = _next()
    customer = Customer(account_number=Customer.next_account_number(),
                        name=name or u'Customer %d' % n, email='buyer%d@example.com' % n,
                        tier=tier, tax_exempt=tax_exempt,
                        credit_limit_cents=credit_limit_cents, **kwargs)
    db.session.add(customer)
    db.session.flush()
    return customer


def make_product(sku=None, price_cents=1000, stock=100, **kwargs):
    n = _next()
    product = Product(sku=sku or 'SKU-%04d' % n, name=kwargs.pop('name', u'Product %d' % n),
                      price_cents=price_cents, stock=stock, reserved=kwargs.pop('reserved', 0),
                      **kwargs)
    db.session.add(product)
    db.session.flush()
    return product


def make_promo(code='SAVE20', percent_off=20, min_subtotal_cents=0, expires_on=None,
               active=True):
    promo = PromoCode(code=code, percent_off=percent_off,
                      min_subtotal_cents=min_subtotal_cents, expires_on=expires_on,
                      active=active)
    db.session.add(promo)
    db.session.flush()
    return promo


def make_order(customer=None, user=None, lines=()):
    """lines is a list of (product, quantity) tuples."""
    customer = customer or make_customer()
    user = user or make_user(role='admin')
    order = workflow.create_order(customer, user)
    for product, quantity in lines:
        workflow.add_line(order, product, quantity, user)
    db.session.flush()
    return order


def advance(order, user, status):
    """Push an order through the workflow up to ``status``."""
    path = ['submitted', 'approved', 'shipped', 'invoiced']
    steps = {
        'submitted': workflow.submit_order,
        'approved': workflow.approve_order,
        'shipped': workflow.ship_order,
        'invoiced': workflow.invoice_order,
    }
    for target in path[:path.index(status) + 1]:
        steps[target](order, user)
    db.session.flush()
    return order
