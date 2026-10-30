from datetime import datetime

import mock
from nose.tools import eq_

from orderdesk import workflow
from orderdesk.extensions import db
from orderdesk.models import AuditEntry, Order
from orderdesk.money import Money

from base import AppTestCase
from factories import (advance, make_customer, make_order, make_product, make_promo,
                       make_user)


class WorkflowTestCase(AppTestCase):

    def setUp(self):
        super(WorkflowTestCase, self).setUp()
        self.admin = make_user(role='admin')
        self.clerk = make_user(role='clerk')
        self.customer = make_customer(tax_exempt=True)
        self.widget = make_product(sku='WID-1', price_cents=1000, stock=100)
        self.gadget = make_product(sku='GAD-1', price_cents=2500, stock=10)

    def order(self, lines=None, customer=None):
        if lines is None:
            lines = [(self.widget, 5)]
        return make_order(customer=customer or self.customer, user=self.clerk, lines=lines)

    def actions(self, order):
        # Flask-SQLAlchemy 1.0 sessions don't autoflush
        db.session.flush()
        entries = AuditEntry.query.filter_by(object_type='order', object_id=order.id) \
            .order_by(AuditEntry.id).all()
        return [e.action for e in entries]


class CreateAndEditTest(WorkflowTestCase):

    def test_create_order(self):
        order = workflow.create_order(self.customer, self.clerk, notes=u'rush')
        eq_(order.number, 'SO-000001')
        eq_(order.status, 'draft')
        eq_(order.customer, self.customer)
        eq_(order.created_by_id, self.clerk.id)
        eq_(order.notes, u'rush')
        eq_(self.actions(order), ['create'])

    def test_order_numbers_increment(self):
        first = self.order()
        second = self.order()
        eq_(first.number, 'SO-000001')
        eq_(second.number, 'SO-000002')

    def test_add_line_snapshots_price(self):
        order = self.order(lines=[])
        line = workflow.add_line(order, self.widget, 3, self.clerk)
        self.widget.price_cents = 9999
        eq_(line.unit_price, Money(1000))
        eq_(line.quantity, 3)
        eq_(order.subtotal, Money(3000))

    def test_add_same_product_merges_lines(self):
        order = self.order(lines=[])
        workflow.add_line(order, self.widget, 3, self.clerk)
        workflow.add_line(order, self.widget, 4, self.clerk)
        eq_(len(order.lines), 1)
        eq_(order.lines[0].quantity, 7)

    def test_add_line_rejects_bad_quantity(self):
        order = self.order(lines=[])
        for qty in (0, -1, None):
            self.assertRaises(workflow.WorkflowError, workflow.add_line,
                              order, self.widget, qty, self.clerk)

    def test_add_line_rejects_discontinued(self):
        old = make_product(discontinued=True)
        self.assertRaises(workflow.WorkflowError, workflow.add_line,
                          self.order(lines=[]), old, 1, self.clerk)

    def test_cannot_edit_submitted_order(self):
        order = self.order()
        workflow.submit_order(order, self.clerk)
        self.assertRaises(workflow.WorkflowError, workflow.add_line,
                          order, self.gadget, 1, self.clerk)

    def test_remove_line(self):
        order = self.order(lines=[(self.widget, 2), (self.gadget, 1)])
        db.session.flush()
        line_id = order.lines[0].id
        workflow.remove_line(order, line_id, self.clerk)
        eq_(len(order.lines), 1)
        eq_(order.subtotal, Money(2500))
        self.assertTrue('remove_line' in self.actions(order))

    def test_remove_unknown_line(self):
        order = self.order()
        self.assertRaises(workflow.WorkflowError, workflow.remove_line, order, 9999, self.clerk)

    def test_apply_promo(self):
        make_promo('SAVE20', 20)
        order = self.order(lines=[(self.widget, 10)])
        promo = workflow.apply_promo(order, ' save20 ', self.clerk)
        eq_(promo.code, 'SAVE20')
        eq_(order.promo_code, 'SAVE20')
        eq_(order.discount, Money(2000))

    def test_apply_invalid_promo(self):
        make_promo('BIG', 20, min_subtotal_cents=1000000)
        order = self.order()
        self.assertRaises(workflow.WorkflowError, workflow.apply_promo, order, 'BIG', self.clerk)
        self.assertRaises(workflow.WorkflowError, workflow.apply_promo, order, 'NOPE', self.clerk)
        eq_(order.promo_code, None)

    def test_clear_promo(self):
        make_promo('SAVE20', 20)
        order = self.order()
        workflow.apply_promo(order, 'SAVE20', self.clerk)
        eq_(workflow.apply_promo(order, '', self.clerk), None)
        eq_(order.promo_code, None)
        eq_(order.discount, Money(0))

    def test_allowed_actions(self):
        order = self.order()
        eq_(order.allowed_actions(), ['submit', 'cancel'])
        advance(order, self.admin, 'shipped')
        eq_(order.allowed_actions(), ['invoice'])


class SubmitTest(WorkflowTestCase):

    def test_submit_reserves_stock(self):
        order = self.order(lines=[(self.widget, 5), (self.gadget, 2)])
        workflow.submit_order(order, self.clerk)
        eq_(order.status, 'submitted')
        self.assertTrue(isinstance(order.submitted_at, datetime))
        eq_(self.widget.reserved, 5)
        eq_(self.gadget.reserved, 2)
        eq_(self.widget.stock, 100)

    def test_submit_empty_order(self):
        order = self.order(lines=[])
        self.assertRaises(workflow.WorkflowError, workflow.submit_order, order, self.clerk)
        eq_(order.status, 'draft')

    def test_insufficient_stock_rolls_back_reservations(self):
        order = self.order(lines=[(self.widget, 5), (self.gadget, 11)])
        try:
            workflow.submit_order(order, self.clerk)
        except workflow.WorkflowError, e:
            self.assertTrue('GAD-1' in str(e))
        else:
            self.fail('expected WorkflowError')
        eq_(order.status, 'draft')
        eq_(self.widget.reserved, 0)
        eq_(self.gadget.reserved, 0)

    def test_credit_limit(self):
        customer = make_customer(tax_exempt=True, credit_limit_cents=10000)
        first = self.order(customer=customer, lines=[(self.widget, 5)])   # $65.00
        workflow.submit_order(first, self.clerk)
        db.session.flush()

        second = self.order(customer=customer, lines=[(self.widget, 5)])
        self.assertRaises(workflow.WorkflowError, workflow.submit_order, second, self.clerk)
        eq_(second.status, 'draft')
        eq_(self.widget.reserved, 5)

    def test_no_credit_limit_means_unlimited(self):
        order = self.order(lines=[(self.widget, 100)])
        workflow.submit_order(order, self.clerk)
        eq_(order.status, 'submitted')


class TransitionTest(WorkflowTestCase):

    def test_only_admin_can_approve(self):
        order = self.order()
        workflow.submit_order(order, self.clerk)
        self.assertRaises(workflow.WorkflowError, workflow.approve_order, order, self.clerk)
        self.assertRaises(workflow.WorkflowError, workflow.approve_order, order, None)
        workflow.approve_order(order, self.admin)
        eq_(order.status, 'approved')

    def test_cannot_skip_steps(self):
        order = self.order()
        self.assertRaises(workflow.WorkflowError, workflow.ship_order, order, self.admin)
        self.assertRaises(workflow.WorkflowError, workflow.approve_order, order, self.admin)
        self.assertRaises(workflow.WorkflowError, workflow.invoice_order, order, self.admin)

    def test_ship_takes_stock(self):
        order = self.order(lines=[(self.widget, 5)])
        advance(order, self.admin, 'shipped')
        eq_(order.status, 'shipped')
        self.assertTrue(order.shipped_at is not None)
        eq_(self.widget.stock, 95)
        eq_(self.widget.reserved, 0)

    def test_invoice(self):
        order = self.order()
        advance(order, self.admin, 'invoiced')
        eq_(order.status, 'invoiced')
        self.assertTrue(order.invoiced_at is not None)
        eq_(order.allowed_actions(), [])

    def test_cancel_draft(self):
        order = self.order()
        workflow.cancel_order(order, self.clerk, u'duplicate')
        eq_(order.status, 'cancelled')
        eq_(self.widget.reserved, 0)

    def test_cancel_submitted_releases_stock(self):
        order = self.order(lines=[(self.widget, 5)])
        workflow.submit_order(order, self.clerk)
        eq_(self.widget.reserved, 5)
        workflow.cancel_order(order, self.clerk)
        eq_(order.status, 'cancelled')
        eq_(self.widget.reserved, 0)

    def test_cannot_cancel_after_shipping(self):
        order = self.order()
        advance(order, self.admin, 'shipped')
        self.assertRaises(workflow.WorkflowError, workflow.cancel_order, order, self.admin)

    def test_audit_trail(self):
        order = self.order()
        advance(order, self.admin, 'invoiced')
        eq_(self.actions(order), ['create', 'add_line', 'submit', 'approve', 'ship', 'invoice'])

    def test_customer_open_balance(self):
        submitted = self.order(lines=[(self.widget, 1)])
        workflow.submit_order(submitted, self.clerk)
        invoiced = self.order(lines=[(self.widget, 2)])
        advance(invoiced, self.admin, 'invoiced')
        self.order(lines=[(self.widget, 3)])  # draft
        db.session.flush()
        eq_(self.customer.open_balance(), submitted.total)

    @mock.patch('orderdesk.workflow.notifications.notify')
    def test_transitions_send_notifications(self, notify):
        order = self.order()
        advance(order, self.admin, 'approved')
        eq_([c[0][0] for c in notify.call_args_list], ['order.submitted', 'order.approved'])
        payload = notify.call_args_list[0][0][1]
        eq_(payload['number'], order.number)
        eq_(payload['customer'], self.customer.account_number)
        eq_(payload['total_cents'], order.total_cents)
