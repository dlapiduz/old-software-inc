# -*- coding: utf-8 -*-
from datetime import date
from decimal import Decimal

from nose.tools import eq_

from orderdesk import pricing
from orderdesk.money import Money

from base import AppTestCase
from factories import make_customer, make_order, make_product, make_promo


class PricingHelpersTest(AppTestCase):

    def test_percent_of(self):
        eq_(pricing.percent_of(Money(10000), 15), Money(1500))
        eq_(pricing.percent_of(Money(999), 10), Money(100))  # 99.9 rounds up

    def test_volume_discount_starts_at_break(self):
        eq_(pricing.volume_discount(Money(1000), pricing.VOLUME_BREAK - 1), Money(0))
        eq_(pricing.volume_discount(Money(1000), pricing.VOLUME_BREAK), Money(3000))


class PriceOrderTest(AppTestCase):

    def setUp(self):
        super(PriceOrderTest, self).setUp()
        self.widget = make_product(price_cents=1000)
        self.gadget = make_product(price_cents=2500)

    def exempt(self, tier='standard'):
        return make_customer(tier=tier, tax_exempt=True)

    def test_subtotal_tax_and_shipping(self):
        order = make_order(lines=[(self.widget, 3), (self.gadget, 2)])
        eq_(order.subtotal, Money(8000))
        eq_(order.tax, Money(660))
        eq_(order.shipping, Money(1500))
        eq_(order.total, Money(10160))
        eq_(order.discount_reason, None)

    def test_tax_on_round_number(self):
        product = make_product(price_cents=10000)
        order = make_order(lines=[(product, 1)])
        eq_(order.tax_cents, 825)
        eq_(order.total_cents, 10000 + 825 + 1500)

    def test_tax_rate_can_be_overridden(self):
        product = make_product(price_cents=10000)
        order = make_order(lines=[(product, 1)])
        quote = pricing.price_order(order, tax_rate='0.10')
        eq_(quote.tax, Money(1000))

    def test_tax_exempt_customer_pays_no_tax(self):
        order = make_order(customer=self.exempt(), lines=[(self.widget, 3)])
        eq_(order.tax, Money(0))
        eq_(order.total, Money(3000 + 1500))

    def test_tax_is_charged_after_tier_discount(self):
        # A gold customer gets a 10% tier discount. One unit at 100000 cents
        # stays below the volume break, so the tier discount is the only one.
        # Tax must be 8.25% of the discounted $900.00 (= $74.25), not of the
        # undiscounted $1,000.00 (= $82.50).
        product = make_product(price_cents=100000)
        order = make_order(customer=make_customer(tier='gold'), lines=[(product, 1)])
        eq_(order.subtotal, Money(100000))
        eq_(order.discount, Money(10000))
        eq_(order.tax_cents, 7425)

    def test_tax_is_charged_after_promo_discount(self):
        # A 20% promo code on a $100.00 order (standard tier, no tier
        # discount) takes off $20.00. Tax is 8.25% of the remaining $80.00
        # (= $6.60), not of the original $100.00 (= $8.25).
        make_promo('SAVE20', 20)
        order = make_order(lines=[(self.widget, 10)])
        order.promo_code = 'SAVE20'
        order.recalculate()
        eq_(order.discount, Money(2000))
        eq_(order.tax, Money(660))

    def test_tax_is_charged_after_volume_discount(self):
        # 100 units reaches the volume break, giving a 3% line discount of
        # $30.00 on a $1,000.00 line. Tax is 8.25% of the discounted $970.00,
        # so the volume discount also reduces the tax base.
        order = make_order(lines=[(self.widget, 100)])
        eq_(order.line_discount, Money(3000))
        eq_(order.tax, Money(97000) * Decimal('0.0825'))

    def test_tax_exempt_customer_pays_no_tax_with_discount(self):
        # Guards the tax_exempt check: a discounted order for an exempt
        # customer must still have $0.00 tax.
        order = make_order(customer=self.exempt('gold'), lines=[(self.widget, 10)])
        eq_(order.discount, Money(1000))
        eq_(order.tax, Money(0))

    def test_volume_discount_on_line(self):
        order = make_order(customer=self.exempt(), lines=[(self.widget, 100)])
        line = order.lines[0]
        eq_(line.gross, Money(100000))
        eq_(line.discount, Money(3000))
        eq_(line.total, Money(97000))
        eq_(order.line_discount, Money(3000))
        eq_(order.shipping, Money(0))
        eq_(order.total, Money(97000))

    def test_no_volume_discount_below_break(self):
        order = make_order(customer=self.exempt(), lines=[(self.widget, 99)])
        eq_(order.line_discount, Money(0))

    def test_tier_discount(self):
        order = make_order(customer=self.exempt('gold'), lines=[(self.widget, 10)])
        eq_(order.discount, Money(1000))
        eq_(order.discount_reason, 'tier:gold')
        eq_(order.total, Money(9000 + 1500))

    def test_each_tier(self):
        for tier, pct in pricing.TIER_DISCOUNTS.iteritems():
            order = make_order(customer=self.exempt(tier), lines=[(self.widget, 10)])
            eq_(order.discount, Money(10000 * pct / 100))

    def test_promo_beats_smaller_tier_discount(self):
        make_promo('SAVE20', 20)
        order = make_order(customer=self.exempt('silver'), lines=[(self.widget, 10)])
        order.promo_code = 'SAVE20'
        order.recalculate()
        eq_(order.discount, Money(2000))
        eq_(order.discount_reason, 'promo:SAVE20')
        eq_(order.total, Money(8000 + 1500))

    def test_tier_beats_smaller_promo(self):
        make_promo('LITTLE', 5)
        order = make_order(customer=self.exempt('gold'), lines=[(self.widget, 10)])
        order.promo_code = 'LITTLE'
        order.recalculate()
        eq_(order.discount, Money(1000))
        eq_(order.discount_reason, 'tier:gold')

    def test_promo_code_is_case_insensitive(self):
        make_promo('SAVE20', 20)
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'save20'
        order.recalculate()
        eq_(order.discount_reason, 'promo:SAVE20')

    def test_expired_promo_is_ignored(self):
        make_promo('OLD', 20, expires_on=date(2000, 1, 1))
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'OLD'
        order.recalculate()
        eq_(order.discount, Money(0))
        eq_(order.discount_reason, None)

    def test_promo_valid_on_expiry_day(self):
        make_promo('LASTDAY', 20, expires_on=date(2014, 6, 30))
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'LASTDAY'
        quote = pricing.price_order(order, today=date(2014, 6, 30))
        eq_(quote.discount, Money(2000))
        quote = pricing.price_order(order, today=date(2014, 7, 1))
        eq_(quote.discount, Money(0))

    def test_inactive_promo_is_ignored(self):
        make_promo('NOPE', 50, active=False)
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'NOPE'
        order.recalculate()
        eq_(order.discount, Money(0))

    def test_promo_minimum_subtotal(self):
        make_promo('BIG', 20, min_subtotal_cents=20000)
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'BIG'
        order.recalculate()
        eq_(order.discount, Money(0))

        order.lines[0].quantity = 20
        order.recalculate()
        eq_(order.discount, Money(4000))

    def test_unknown_promo_is_ignored(self):
        order = make_order(customer=self.exempt(), lines=[(self.widget, 10)])
        order.promo_code = 'WHATEVER'
        order.recalculate()
        eq_(order.discount, Money(0))

    def test_free_shipping_threshold(self):
        big = make_product(price_cents=50000)
        order = make_order(customer=self.exempt(), lines=[(big, 1)])
        eq_(order.shipping, Money(0))

        almost = make_product(price_cents=49999)
        order = make_order(customer=self.exempt(), lines=[(almost, 1)])
        eq_(order.shipping, Money(1500))

    def test_free_shipping_uses_discounted_amount(self):
        product = make_product(price_cents=52000)
        order = make_order(customer=self.exempt('gold'), lines=[(product, 1)])
        eq_(order.discount, Money(5200))
        eq_(order.shipping, Money(1500))

    def test_empty_order(self):
        order = make_order()
        eq_(order.subtotal, Money(0))
        eq_(order.shipping, Money(0))
        eq_(order.total, Money(0))

    def test_recalculate_stores_cents(self):
        order = make_order(customer=self.exempt('gold'), lines=[(self.widget, 10)])
        eq_(order.subtotal_cents, 10000)
        eq_(order.discount_cents, 1000)
        eq_(order.shipping_cents, 1500)
        eq_(order.total_cents, 10500)
