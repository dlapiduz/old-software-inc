# -*- coding: utf-8 -*-
from nose.tools import eq_

from orderdesk.models import Order, Product

from base import AppTestCase
from factories import advance, make_customer, make_order, make_product, make_promo, make_user


class ApiTest(AppTestCase):

    def setUp(self):
        super(ApiTest, self).setUp()
        self.admin = make_user(role='admin')
        self.clerk = make_user(role='clerk')
        self.customer = make_customer(tax_exempt=True)
        self.widget = make_product(sku='WID-1001', price_cents=125, stock=500)
        self.old = make_product(sku='WID-0999', discontinued=True)

    def test_requires_token(self):
        eq_(self.api('get', '/products').status_code, 401)
        resp = self.client.get('/api/v1/products', headers={'X-OrderDesk-Token': 'bogus'})
        eq_(resp.status_code, 401)

    def test_inactive_user_token_rejected(self):
        user = make_user(active=False)
        eq_(self.api('get', '/products', user).status_code, 401)

    def test_token_in_query_string(self):
        resp = self.client.get('/api/v1/products?token=%s' % self.clerk.api_token)
        eq_(resp.status_code, 200)

    def test_list_products(self):
        resp = self.api('get', '/products', self.clerk)
        eq_(resp.status_code, 200)
        eq_([p['sku'] for p in resp.json_body['products']], ['WID-1001'])
        product = resp.json_body['products'][0]
        eq_(product['price_cents'], 125)
        eq_(product['price'], '$1.25')
        eq_(product['available'], 500)

        resp = self.api('get', '/products?include_discontinued=1', self.clerk)
        eq_(len(resp.json_body['products']), 2)

    def test_get_product(self):
        resp = self.api('get', '/products/wid-1001', self.clerk)
        eq_(resp.json_body['product']['sku'], 'WID-1001')
        eq_(self.api('get', '/products/NOPE', self.clerk).status_code, 404)

    def test_list_orders(self):
        draft = make_order(customer=self.customer, user=self.clerk, lines=[(self.widget, 1)])
        submitted = make_order(customer=self.customer, user=self.clerk, lines=[(self.widget, 1)])
        advance(submitted, self.admin, 'submitted')

        resp = self.api('get', '/orders', self.clerk)
        eq_(sorted(o['number'] for o in resp.json_body['orders']),
            [draft.number, submitted.number])
        self.assertFalse('lines' in resp.json_body['orders'][0])

        resp = self.api('get', '/orders?status=submitted', self.clerk)
        eq_([o['number'] for o in resp.json_body['orders']], [submitted.number])

        eq_(self.api('get', '/orders?status=lost', self.clerk).status_code, 400)

    def test_get_order(self):
        order = make_order(customer=self.customer, user=self.clerk, lines=[(self.widget, 4)])
        resp = self.api('get', '/orders/%s' % order.number, self.clerk)
        eq_(resp.status_code, 200)
        body = resp.json_body['order']
        eq_(body['number'], order.number)
        eq_(body['customer'], self.customer.account_number)
        eq_(body['status'], 'draft')
        eq_(body['subtotal_cents'], 500)
        eq_(body['total_cents'], 2000)
        eq_(body['lines'][0]['sku'], 'WID-1001')
        eq_(body['lines'][0]['quantity'], 4)

        eq_(self.api('get', '/orders/SO-424242', self.clerk).status_code, 404)

    def test_create_order(self):
        resp = self.api('post', '/orders', self.clerk, {
            'customer': self.customer.account_number,
            'notes': u'EDI PO #7781',
            'lines': [{'sku': 'WID-1001', 'quantity': 200}],
        })
        eq_(resp.status_code, 201)
        body = resp.json_body['order']
        eq_(body['status'], 'draft')
        eq_(body['notes'], u'EDI PO #7781')
        eq_(body['subtotal_cents'], 25000)
        eq_(body['line_discount_cents'], 750)
        eq_(Order.query.count(), 1)

    def test_create_and_submit_with_promo(self):
        make_promo('EDI10', 10)
        resp = self.api('post', '/orders', self.clerk, {
            'customer': self.customer.account_number,
            'lines': [{'sku': 'WID-1001', 'quantity': 10}],
            'promo_code': 'edi10',
            'submit': True,
        })
        eq_(resp.status_code, 201)
        body = resp.json_body['order']
        eq_(body['status'], 'submitted')
        eq_(body['promo_code'], 'EDI10')
        eq_(body['discount_cents'], 125)
        eq_(Product.query.get(self.widget.id).reserved, 10)

    def test_create_order_errors(self):
        eq_(self.api('post', '/orders', self.clerk, ['not', 'a', 'dict']).status_code, 400)
        eq_(self.api('post', '/orders', self.clerk, {'customer': 'C-99999',
                                                     'lines': [{'sku': 'WID-1001'}]}).status_code,
            400)
        eq_(self.api('post', '/orders', self.clerk, {'customer': self.customer.account_number,
                                                     'lines': []}).status_code, 400)

        resp = self.api('post', '/orders', self.clerk, {
            'customer': self.customer.account_number,
            'lines': [{'sku': 'WID-1001', 'quantity': 1}, {'sku': 'NOPE', 'quantity': 1}],
        })
        eq_(resp.status_code, 422)
        eq_(resp.json_body['error'], 'unknown sku NOPE')
        eq_(Order.query.count(), 0)

        resp = self.api('post', '/orders', self.clerk, {
            'customer': self.customer.account_number,
            'lines': [{'sku': 'WID-1001', 'quantity': 'lots'}],
        })
        eq_(resp.status_code, 422)

    def test_create_order_insufficient_stock(self):
        resp = self.api('post', '/orders', self.clerk, {
            'customer': self.customer.account_number,
            'lines': [{'sku': 'WID-1001', 'quantity': 501}],
            'submit': True,
        })
        eq_(resp.status_code, 422)
        self.assertTrue('Insufficient stock' in resp.json_body['error'])
        eq_(Order.query.count(), 0)

    def test_order_actions(self):
        order = make_order(customer=self.customer, user=self.clerk, lines=[(self.widget, 1)])
        number = order.number

        resp = self.api('post', '/orders/%s/submit' % number, self.clerk)
        eq_(resp.json_body['order']['status'], 'submitted')

        resp = self.api('post', '/orders/%s/approve' % number, self.clerk)
        eq_(resp.status_code, 422)
        eq_(resp.json_body['error'], 'Only administrators can approve orders')

        resp = self.api('post', '/orders/%s/approve' % number, self.admin)
        eq_(resp.json_body['order']['status'], 'approved')

        eq_(self.api('post', '/orders/%s/explode' % number, self.admin).status_code, 404)
        eq_(self.api('post', '/orders/SO-999999/ship', self.admin).status_code, 404)
