# -*- coding: utf-8 -*-
from datetime import datetime

from nose.tools import eq_

from orderdesk.extensions import db
from orderdesk.models import AuditEntry, Customer, Order, Product

from base import AppTestCase
from factories import advance, make_customer, make_order, make_product, make_user


class AuthViewsTest(AppTestCase):

    def test_login_page(self):
        resp = self.client.get('/login')
        eq_(resp.status_code, 200)
        self.assertTrue('Log in' in resp.data)

    def test_dashboard_requires_login(self):
        resp = self.client.get('/')
        eq_(resp.status_code, 302)
        self.assertTrue('/login' in resp.headers['Location'])

    def test_login_and_logout(self):
        user = make_user(username='gary')
        resp = self.login(user)
        eq_(resp.status_code, 200)
        self.assertTrue('Dashboard' in resp.data)
        self.assertTrue('gary (clerk)' in resp.data)
        eq_(AuditEntry.query.filter_by(action='login').count(), 1)

        resp = self.logout()
        self.assertTrue('You have been logged out' in resp.data)
        eq_(self.client.get('/').status_code, 302)

    def test_bad_password(self):
        user = make_user()
        resp = self.login(user, password='wrong')
        self.assertTrue('Invalid username or password' in resp.data)
        eq_(self.client.get('/').status_code, 302)

    def test_inactive_user_cannot_log_in(self):
        user = make_user(active=False)
        resp = self.login(user)
        self.assertTrue('Invalid username or password' in resp.data)

    def test_login_redirects_to_next(self):
        user = make_user()
        db.session.commit()
        resp = self.client.post('/login?next=/customers',
                                data={'username': user.username, 'password': 'secret'})
        eq_(resp.status_code, 302)
        self.assertTrue(resp.headers['Location'].endswith('/customers'))


class DashboardTest(AppTestCase):

    def test_dashboard(self):
        admin = make_user(role='admin')
        make_product(sku='LOW-1', stock=2)
        make_order(user=admin, lines=[(make_product(sku='OK-1'), 1)])
        self.login(admin)
        resp = self.client.get('/')
        eq_(resp.status_code, 200)
        self.assertTrue('SO-000001' in resp.data)
        self.assertTrue('LOW-1' in resp.data)


class CustomerViewsTest(AppTestCase):

    def setUp(self):
        super(CustomerViewsTest, self).setUp()
        self.clerk = make_user(role='clerk')
        self.login(self.clerk)

    def test_list_and_search(self):
        make_customer(name=u'Acme Industrial Supply')
        make_customer(name=u'Bluebonnet Manufacturing')
        resp = self.client.get('/customers')
        self.assertTrue('Acme Industrial' in resp.data)
        self.assertTrue('Bluebonnet' in resp.data)

        resp = self.client.get('/customers?q=acme')
        self.assertTrue('Acme Industrial' in resp.data)
        self.assertFalse('Bluebonnet' in resp.data)

    def test_unicode_names_render(self):
        make_customer(name=u'Café Müller GmbH')
        resp = self.client.get('/customers')
        self.assertTrue(u'Café Müller GmbH'.encode('utf-8') in resp.data)

    def test_create(self):
        resp = self.client.post('/customers/new', data={
            'name': u'Hill Country Brewing Co.',
            'email': 'beer@hillcountry.example',
            'tier': 'silver',
            'credit_limit_amount': '2500.00',
            'notes': '',
        })
        eq_(resp.status_code, 302)
        customer = Customer.query.filter_by(name=u'Hill Country Brewing Co.').one()
        eq_(customer.account_number, 'C-00001')
        eq_(customer.tier, 'silver')
        eq_(customer.credit_limit_cents, 250000)
        eq_(customer.tax_exempt, False)

    def test_create_validates(self):
        resp = self.client.post('/customers/new', data={'name': '', 'email': 'not-an-email',
                                                        'tier': 'standard'})
        eq_(resp.status_code, 200)
        eq_(Customer.query.count(), 0)
        self.assertTrue('This field is required' in resp.data)
        self.assertTrue('Invalid email address' in resp.data)

    def test_detail(self):
        customer = make_customer(name=u'Joliet Tool & Die', credit_limit_cents=100000)
        resp = self.client.get('/customers/%d' % customer.id)
        eq_(resp.status_code, 200)
        self.assertTrue('Joliet Tool &amp; Die' in resp.data)
        self.assertTrue('$1,000.00' in resp.data)

    def test_edit(self):
        customer = make_customer(name=u'Knoxville Packaging', credit_limit_cents=100000)
        resp = self.client.get('/customers/%d/edit' % customer.id)
        self.assertTrue('1000.00' in resp.data)

        resp = self.client.post('/customers/%d/edit' % customer.id, data={
            'name': u'Knoxville Packaging LLC',
            'tier': 'gold',
            'tax_exempt': 'y',
            'credit_limit_amount': '',
        })
        eq_(resp.status_code, 302)
        customer = Customer.query.get(customer.id)
        eq_(customer.name, u'Knoxville Packaging LLC')
        eq_(customer.tier, 'gold')
        eq_(customer.tax_exempt, True)
        eq_(customer.credit_limit_cents, 0)

    def test_viewer_cannot_create(self):
        self.logout()
        self.login(make_user(role='viewer'))
        eq_(self.client.get('/customers/new').status_code, 403)

    def test_missing_customer(self):
        eq_(self.client.get('/customers/999').status_code, 404)


class ProductViewsTest(AppTestCase):

    def test_admin_can_create_product(self):
        self.login(make_user(role='admin'))
        resp = self.client.post('/products/new', data={
            'sku': 'vlv-7004', 'name': u'Gate Valve 3"', 'price_amount': '149.95',
            'stock': '12', 'description': '',
        })
        eq_(resp.status_code, 302)
        product = Product.query.filter_by(sku='VLV-7004').one()
        eq_(product.price_cents, 14995)
        eq_(product.stock, 12)
        eq_(product.reserved, 0)

    def test_duplicate_sku(self):
        make_product(sku='DUP-1')
        self.login(make_user(role='admin'))
        resp = self.client.post('/products/new', data={
            'sku': 'dup-1', 'name': u'Another', 'price_amount': '1.00', 'stock': '1',
        })
        eq_(resp.status_code, 200)
        self.assertTrue('SKU already exists' in resp.data)

    def test_edit_product(self):
        product = make_product(sku='EDIT-1', price_cents=1000)
        self.login(make_user(role='admin'))
        resp = self.client.get('/products/%d/edit' % product.id)
        self.assertTrue('10.00' in resp.data)
        resp = self.client.post('/products/%d/edit' % product.id, data={
            'sku': 'EDIT-1', 'name': u'Edited', 'price_amount': '12.50', 'stock': '5',
            'discontinued': 'y',
        })
        eq_(resp.status_code, 302)
        product = Product.query.get(product.id)
        eq_(product.price_cents, 1250)
        eq_(product.discontinued, True)

    def test_clerk_cannot_manage_products(self):
        self.login(make_user(role='clerk'))
        eq_(self.client.get('/products').status_code, 200)
        eq_(self.client.get('/products/new').status_code, 403)

    def test_discontinued_hidden_by_default(self):
        make_product(sku='OLD-1', discontinued=True)
        make_product(sku='NEW-1')
        self.login(make_user(role='viewer'))
        resp = self.client.get('/products')
        self.assertFalse('OLD-1' in resp.data)
        self.assertTrue('OLD-1' in self.client.get('/products?show=all').data)


class OrderViewsTest(AppTestCase):

    def setUp(self):
        super(OrderViewsTest, self).setUp()
        self.admin = make_user(role='admin')
        self.clerk = make_user(role='clerk')
        self.customer = make_customer(name=u'Lone Star Pipe Works', tax_exempt=True)
        self.product = make_product(sku='FLG-3001', price_cents=4400, stock=60)

    def test_full_order_flow(self):
        from factories import make_promo
        make_promo('SAVE20', 20)
        self.login(self.admin)

        resp = self.client.post('/orders/new', data={'customer_id': self.customer.id})
        eq_(resp.status_code, 302)
        order = Order.query.one()
        self.assertTrue(resp.headers['Location'].endswith('/orders/%s' % order.number))

        resp = self.client.post('/orders/%s/lines' % order.number,
                                data={'product_id': self.product.id, 'quantity': '3'},
                                follow_redirects=True)
        self.assertTrue('Added 3 x FLG-3001' in resp.data)

        resp = self.client.post('/orders/%s/promo' % order.number, data={'code': 'save20'},
                                follow_redirects=True)
        self.assertTrue('Promo code SAVE20 applied' in resp.data)

        for action, status in [('submit', 'submitted'), ('approve', 'approved'),
                               ('ship', 'shipped'), ('invoice', 'invoiced')]:
            resp = self.client.post('/orders/%s/transition/%s' % (order.number, action),
                                    follow_redirects=True)
            self.assertTrue('is now %s' % status in resp.data, resp.data)

        order = Order.query.one()
        eq_(order.status, 'invoiced')
        eq_(order.total_cents, 13200 - 2640 + 1500)
        eq_(Product.query.get(self.product.id).stock, 57)

    def test_order_list_filters_by_status(self):
        make_order(customer=self.customer, user=self.admin, lines=[(self.product, 1)])
        submitted = make_order(customer=self.customer, user=self.admin, lines=[(self.product, 1)])
        advance(submitted, self.admin, 'submitted')
        self.login(self.clerk)

        resp = self.client.get('/orders?status=submitted')
        self.assertTrue(submitted.number in resp.data)
        self.assertFalse('SO-000001' in resp.data)
        resp = self.client.get('/orders')
        self.assertTrue('SO-000001' in resp.data)

    def test_detail(self):
        order = make_order(customer=self.customer, user=self.admin, lines=[(self.product, 2)])
        self.login(self.clerk)
        resp = self.client.get('/orders/%s' % order.number)
        eq_(resp.status_code, 200)
        self.assertTrue('FLG-3001' in resp.data)
        self.assertTrue('$88.00' in resp.data)
        self.assertTrue('add_line' in resp.data)

    def test_remove_line(self):
        order = make_order(customer=self.customer, user=self.admin, lines=[(self.product, 2)])
        db.session.flush()
        line_id = order.lines[0].id
        self.login(self.clerk)
        resp = self.client.post('/orders/%s/lines/%d/delete' % (order.number, line_id),
                                follow_redirects=True)
        self.assertTrue('Line removed' in resp.data)
        eq_(len(Order.query.get(order.id).lines), 0)

    def test_add_line_with_bad_quantity(self):
        order = make_order(customer=self.customer, user=self.admin)
        self.login(self.clerk)
        resp = self.client.post('/orders/%s/lines' % order.number,
                                data={'product_id': self.product.id, 'quantity': '0'},
                                follow_redirects=True)
        self.assertTrue('Quantity' in resp.data)
        eq_(len(Order.query.get(order.id).lines), 0)

    def test_clerk_cannot_approve(self):
        order = make_order(customer=self.customer, user=self.admin, lines=[(self.product, 1)])
        advance(order, self.admin, 'submitted')
        self.login(self.clerk)
        resp = self.client.post('/orders/%s/transition/approve' % order.number,
                                follow_redirects=True)
        self.assertTrue('Only administrators can approve orders' in resp.data)
        eq_(Order.query.get(order.id).status, 'submitted')

    def test_invalid_transition(self):
        order = make_order(customer=self.customer, user=self.admin, lines=[(self.product, 1)])
        self.login(self.admin)
        resp = self.client.post('/orders/%s/transition/ship' % order.number,
                                follow_redirects=True)
        self.assertTrue('Cannot move order' in resp.data)

    def test_unknown_action_and_order(self):
        order = make_order(customer=self.customer, user=self.admin)
        self.login(self.admin)
        eq_(self.client.post('/orders/%s/transition/explode' % order.number).status_code, 404)
        eq_(self.client.get('/orders/SO-999999').status_code, 404)

    def test_viewer_cannot_create_orders(self):
        self.login(make_user(role='viewer'))
        eq_(self.client.post('/orders/new', data={'customer_id': self.customer.id}).status_code,
            403)


class ReportViewsTest(AppTestCase):

    def setUp(self):
        super(ReportViewsTest, self).setUp()
        self.admin = make_user(role='admin')
        customer = make_customer(name=u'Café Müller GmbH', tax_exempt=True)
        self.order = make_order(customer=customer, user=self.admin,
                                lines=[(make_product(sku='WID-1', price_cents=1000), 10)])
        advance(self.order, self.admin, 'shipped')
        self.order.created_at = datetime(2014, 3, 10, 12, 0)
        self.login(self.admin)

    def test_sales_report(self):
        resp = self.client.get('/reports/sales?start=2014-03-01&end=2014-03-30')
        eq_(resp.status_code, 200)
        self.assertTrue('$115.00' in resp.data)
        self.assertTrue('WID-1' in resp.data)

    def test_sales_report_defaults(self):
        eq_(self.client.get('/reports/sales').status_code, 200)

    def test_orders_csv(self):
        resp = self.client.get('/reports/orders.csv')
        eq_(resp.status_code, 200)
        eq_(resp.mimetype, 'text/csv')
        self.assertTrue('attachment; filename=orders-' in resp.headers['Content-Disposition'])
        self.assertTrue(self.order.number.encode('utf-8') in resp.data)
        self.assertTrue(u'Café Müller GmbH'.encode('utf-8') in resp.data)

    def test_customers_csv(self):
        resp = self.client.get('/reports/customers.csv')
        eq_(resp.status_code, 200)
        self.assertTrue(resp.data.startswith('account_number,name'))
