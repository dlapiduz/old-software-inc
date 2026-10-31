# -*- coding: utf-8 -*-
"""
Order pricing rules.

 * Lines with VOLUME_BREAK or more units get VOLUME_DISCOUNT_PCT off.
 * The order gets the customer's tier discount OR a promo code discount,
   whichever is bigger. They never stack.
 * Sales tax is charged on the discounted merchandise total, unless the
   customer is tax exempt.
 * Flat shipping under FREE_SHIPPING_OVER, free above it.
"""
from decimal import Decimal

from flask import current_app

from money import Money
from models import PromoCode

TIER_DISCOUNTS = {
    'standard': 0,
    'silver': 5,
    'gold': 10,
    'platinum': 15,
}

VOLUME_BREAK = 100
VOLUME_DISCOUNT_PCT = 3

FREE_SHIPPING_OVER = Money(50000)
FLAT_SHIPPING = Money(1500)


class Quote(object):

    def __init__(self):
        self.subtotal = Money(0)
        self.line_discounts = Money(0)
        self.discount = Money(0)
        self.discount_reason = None
        self.tax = Money(0)
        self.shipping = Money(0)

    @property
    def total(self):
        return self.subtotal - self.line_discounts - self.discount + self.tax + self.shipping


def percent_of(amount, pct):
    return amount * (Decimal(pct) / 100)


def volume_discount(unit_price, quantity):
    if quantity >= VOLUME_BREAK:
        return percent_of(unit_price * quantity, VOLUME_DISCOUNT_PCT)
    return Money(0)


def best_order_discount(customer, promo_code, net, today=None):
    """Return (percent, reason) for the best order level discount."""
    candidates = [(TIER_DISCOUNTS.get(customer.tier, 0), 'tier:%s' % customer.tier)]
    if promo_code:
        promo = PromoCode.query.filter_by(code=promo_code.upper()).first()
        if promo is not None and promo.is_valid(net, today):
            candidates.append((promo.percent_off, 'promo:%s' % promo.code))
    candidates = sorted(candidates, cmp=lambda a, b: cmp(b[0], a[0]))
    pct, reason = candidates[0]
    if pct <= 0:
        return 0, None
    return pct, reason


def price_order(order, tax_rate=None, today=None):
    if tax_rate is None:
        tax_rate = current_app.config['TAX_RATE']
    tax_rate = Decimal(str(tax_rate))
    customer = order.customer

    quote = Quote()
    for line in order.lines:
        line.discount = volume_discount(line.unit_price, line.quantity)
        quote.subtotal += line.gross
        quote.line_discounts += line.discount

    net = quote.subtotal - quote.line_discounts
    pct, reason = best_order_discount(customer, order.promo_code, net, today)
    if pct:
        quote.discount = percent_of(net, pct)
        quote.discount_reason = reason

    merchandise = net - quote.discount
    if not customer.tax_exempt:
        quote.tax = merchandise * tax_rate
    if order.lines and merchandise < FREE_SHIPPING_OVER:
        quote.shipping = FLAT_SHIPPING
    return quote
