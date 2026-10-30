# -*- coding: utf-8 -*-
import unittest
from datetime import date

from nose.tools import eq_

from orderdesk.models import Product
from orderdesk.utils import paginate, parse_date, slugify

from base import AppTestCase
from factories import make_product


class SlugifyTest(unittest.TestCase):

    def test_slugify(self):
        eq_(slugify(u'Café Müller GmbH'), 'cafe-muller-gmbh')
        eq_(slugify('Hex Bolt 1/2-13 x 2"'), 'hex-bolt-12-13-x-2')
        eq_(slugify(u'  Société   Générale  '), 'societe-generale')

    def test_slugify_accepts_utf8_bytes(self):
        eq_(slugify(u'Peñasco'.encode('utf-8')), 'penasco')


class ParseDateTest(unittest.TestCase):

    def test_parse_date(self):
        eq_(parse_date('2014-03-31'), date(2014, 3, 31))
        eq_(parse_date('03/31/2014'), date(2014, 3, 31))

    def test_parse_date_bad_input(self):
        eq_(parse_date(''), None)
        eq_(parse_date(None), None)
        eq_(parse_date('not a date'), None)


class PaginateTest(AppTestCase):

    def setUp(self):
        super(PaginateTest, self).setUp()
        for i in xrange(40):
            make_product(sku='P-%03d' % i)

    def query(self):
        return Product.query.order_by(Product.sku)

    def test_first_page(self):
        page = paginate(self.query(), 1, per_page=20)
        eq_(page.total, 40)
        eq_(page.pages, 2)
        eq_(len(page.items), 20)
        eq_(page.items[0].sku, 'P-000')
        self.assertFalse(page.has_prev)
        self.assertTrue(page.has_next)
        eq_(page.next_num, 2)

    def test_last_page(self):
        page = paginate(self.query(), 2, per_page=20)
        eq_(page.items[0].sku, 'P-020')
        self.assertTrue(page.has_prev)
        self.assertFalse(page.has_next)

    def test_page_below_one(self):
        eq_(paginate(self.query(), 0, per_page=20).page, 1)

    def test_default_per_page(self):
        eq_(paginate(self.query()).per_page, self.app.config['ITEMS_PER_PAGE'])

    def test_empty(self):
        page = paginate(Product.query.filter_by(sku='nope'), 1, per_page=20)
        eq_(page.items, [])
        eq_(page.pages, 1)
        self.assertFalse(page.has_next)
