# -*- coding: utf-8 -*-
import cStringIO

import unicodecsv

ORDER_HEADER = ['number', 'created_at', 'customer', 'customer_name', 'status',
                'promo_code', 'subtotal', 'discount', 'tax', 'shipping', 'total']

CUSTOMER_HEADER = ['account_number', 'name', 'email', 'phone', 'tier',
                   'tax_exempt', 'credit_limit']


def _amount(money):
    return u'%.2f' % money.as_decimal()


def export_orders(orders):
    buf = cStringIO.StringIO()
    writer = unicodecsv.writer(buf, encoding='utf-8')
    writer.writerow(ORDER_HEADER)
    for o in orders:
        writer.writerow([
            o.number,
            o.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            o.customer.account_number,
            o.customer.name,
            o.status,
            o.promo_code or u'',
            _amount(o.subtotal),
            _amount(o.line_discount + o.discount),
            _amount(o.tax),
            _amount(o.shipping),
            _amount(o.total),
        ])
    return buf.getvalue()


def export_customers(customers):
    buf = cStringIO.StringIO()
    writer = unicodecsv.writer(buf, encoding='utf-8')
    writer.writerow(CUSTOMER_HEADER)
    for c in customers:
        writer.writerow([
            c.account_number,
            c.name,
            c.email or u'',
            c.phone or u'',
            c.tier,
            c.tax_exempt and u'Y' or u'N',
            _amount(c.credit_limit),
        ])
    return buf.getvalue()
