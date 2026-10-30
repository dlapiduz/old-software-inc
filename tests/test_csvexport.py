# -*- coding: utf-8 -*-
import cStringIO
from datetime import datetime

import unicodecsv
from nose.tools import eq_

from orderdesk import csvexport

from base import AppTestCase
from factories import make_customer, make_order, make_product


def _rows(data):
    return list(unicodecsv.reader(cStringIO.StringIO(data), encoding='utf-8'))


class CsvExportTest(AppTestCase):

    def test_export_orders(self):
        customer = make_customer(name=u'Café Müller GmbH', tax_exempt=True)
        order = make_order(customer=customer, lines=[(make_product(price_cents=1999), 2)])
        order.created_at = datetime(2014, 3, 1, 8, 30, 0)
        data = csvexport.export_orders([order])
        self.assertTrue(isinstance(data, str))

        rows = _rows(data)
        eq_(rows[0], csvexport.ORDER_HEADER)
        eq_(rows[1], [order.number, u'2014-03-01 08:30:00', customer.account_number,
                      u'Café Müller GmbH', u'draft', u'', u'39.98', u'0.00', u'0.00',
                      u'15.00', u'54.98'])

    def test_export_orders_empty(self):
        eq_(_rows(csvexport.export_orders([])), [csvexport.ORDER_HEADER])

    def test_export_customers(self):
        make_customer(name=u'Industrias Peñasco, S.A.', tier='gold', tax_exempt=True,
                      credit_limit_cents=150000, phone='555-0100')
        from orderdesk.models import Customer
        rows = _rows(csvexport.export_customers(Customer.query.all()))
        eq_(rows[0], csvexport.CUSTOMER_HEADER)
        eq_(rows[1][1], u'Industrias Peñasco, S.A.')
        eq_(rows[1][3:], [u'555-0100', u'gold', u'Y', u'1500.00'])
