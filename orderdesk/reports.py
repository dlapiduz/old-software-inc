# -*- coding: utf-8 -*-
import cPickle
from datetime import datetime

from flask import current_app

from extensions import db
from models import CUSTOMER_TIERS, Order, ReportCache
from money import Money

REVENUE_STATUSES = ('shipped', 'invoiced')


def _day_start(d):
    return datetime(d.year, d.month, d.day)


def _orders_between(start=None, end=None):
    """Revenue orders created between start and end (inclusive dates)."""
    query = Order.query.filter(Order.status.in_(REVENUE_STATUSES))
    if start is not None:
        query = query.filter(Order.created_at >= _day_start(start))
    if end is not None:
        query = query.filter(Order.created_at < _day_start(end))
    return query.order_by(Order.created_at).all()


def cached_report(key, builder, max_age=None):
    if max_age is None:
        max_age = current_app.config['REPORT_CACHE_SECONDS']
    entry = ReportCache.query.get(key)
    if entry is not None and (datetime.utcnow() - entry.created_at).seconds < max_age:
        return cPickle.loads(str(entry.payload))

    data = builder()
    if entry is None:
        entry = ReportCache(key=key)
        db.session.add(entry)
    entry.created_at = datetime.utcnow()
    entry.payload = cPickle.dumps(data, cPickle.HIGHEST_PROTOCOL)
    db.session.commit()
    return data


def _build_sales_summary(start, end):
    orders = _orders_between(start, end)
    revenue = sum((o.total for o in orders), Money(0))
    if orders:
        average = revenue / len(orders)
    else:
        average = Money(0)

    by_tier = {}
    for tier in CUSTOMER_TIERS:
        tier_orders = filter(lambda o: o.customer.tier == tier, orders)
        by_tier[tier] = reduce(lambda acc, o: acc + o.total, tier_orders, Money(0))

    return {
        'start': start,
        'end': end,
        'count': len(orders),
        'revenue': revenue,
        'average': average,
        'by_tier': by_tier,
    }


def sales_summary(start=None, end=None):
    key = 'sales_summary:%s:%s' % (start, end)
    return cached_report(key, lambda: _build_sales_summary(start, end))


def top_products(start=None, end=None, limit=5):
    totals = {}
    for order in _orders_between(start, end):
        for line in order.lines:
            if not totals.has_key(line.product_id):
                totals[line.product_id] = {
                    'sku': line.product.sku,
                    'name': line.product.name,
                    'quantity': 0,
                    'revenue': Money(0),
                }
            totals[line.product_id]['quantity'] += line.quantity
            totals[line.product_id]['revenue'] += line.total
    ranked = sorted(totals.itervalues(), key=lambda e: e['quantity'], reverse=True)
    return ranked[:limit]
