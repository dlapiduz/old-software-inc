# -*- coding: utf-8 -*-
from datetime import date, datetime

from nose.tools import eq_

from orderdesk import reports
from orderdesk.models import ReportCache
from orderdesk.money import Money

from base import AppTestCase
from factories import advance, make_customer, make_order, make_product, make_user


class ReportsTest(AppTestCase):

    def setUp(self):
        super(ReportsTest, self).setUp()
        self.admin = make_user(role='admin')
        standard = make_customer(tier='standard', tax_exempt=True)
        silver = make_customer(tier='silver', tax_exempt=True)
        self.widget = make_product(sku='WID-1', name=u'Widget', price_cents=1000, stock=1000)
        self.gadget = make_product(sku='GAD-1', name=u'Gadget', price_cents=1000, stock=1000)

        # $115.00
        self.a = self._order(standard, [(self.widget, 10)], 'shipped', datetime(2014, 3, 10, 9, 0))
        # $200.00 - 5% + $15.00 = $205.00
        self.b = self._order(silver, [(self.gadget, 20)], 'invoiced', datetime(2014, 3, 15, 14, 30))
        # $65.00
        self.c = self._order(standard, [(self.widget, 5)], 'shipped', datetime(2014, 3, 20, 16, 45))

        # not revenue
        self._order(standard, [(self.widget, 50)], 'submitted', datetime(2014, 3, 12))
        self._order(standard, [(self.widget, 50)], None, datetime(2014, 3, 12))
        # out of range
        self._order(standard, [(self.widget, 7)], 'shipped', datetime(2014, 2, 27, 10, 0))

    def _order(self, customer, lines, status, created_at):
        order = make_order(customer=customer, user=self.admin, lines=lines)
        if status:
            advance(order, self.admin, status)
        order.created_at = created_at
        return order

    def test_sales_summary(self):
        summary = reports.sales_summary(date(2014, 3, 1), date(2014, 3, 30))
        eq_(summary['count'], 3)
        eq_(summary['revenue'], Money(11500 + 20500 + 6500))
        eq_(summary['average'], Money(12833))  # 38500 / 3, rounded down
        eq_(summary['by_tier']['standard'], Money(18000))
        eq_(summary['by_tier']['silver'], Money(20500))
        eq_(summary['by_tier']['gold'], Money(0))
        eq_(summary['start'], date(2014, 3, 1))

    def test_sales_summary_without_range(self):
        summary = reports.sales_summary()
        eq_(summary['count'], 4)

    def test_sales_summary_empty(self):
        summary = reports.sales_summary(date(2010, 1, 1), date(2010, 1, 31))
        eq_(summary['count'], 0)
        eq_(summary['revenue'], Money(0))
        eq_(summary['average'], Money(0))

    def test_top_products(self):
        top = reports.top_products(date(2014, 3, 1), date(2014, 3, 30))
        eq_([row['sku'] for row in top], ['GAD-1', 'WID-1'])
        eq_(top[0]['quantity'], 20)
        eq_(top[1]['quantity'], 15)
        eq_(top[1]['revenue'], Money(15000))
        eq_(top[1]['name'], u'Widget')

    def test_top_products_limit(self):
        eq_(len(reports.top_products(limit=1)), 1)


class ReportCacheTest(AppTestCase):

    def test_cache_hit(self):
        first = reports.cached_report('k', lambda: {'total': Money(1)}, max_age=300)
        second = reports.cached_report('k', lambda: {'total': Money(2)}, max_age=300)
        eq_(first, {'total': Money(1)})
        eq_(second, {'total': Money(1)})
        eq_(ReportCache.query.count(), 1)

    def test_cache_disabled(self):
        reports.cached_report('k', lambda: 1, max_age=0)
        eq_(reports.cached_report('k', lambda: 2, max_age=0), 2)
        eq_(ReportCache.query.count(), 1)

    def test_cached_values_round_trip(self):
        data = {'when': date(2014, 3, 1), 'amount': Money(-1234), 'name': u'Café'}
        reports.cached_report('rt', lambda: data, max_age=300)
        eq_(reports.cached_report('rt', lambda: None, max_age=300), data)
