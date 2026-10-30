# -*- coding: utf-8 -*-
import unittest
from decimal import Decimal

from nose.tools import eq_, raises

from orderdesk.money import Money


class MoneyTest(unittest.TestCase):

    def test_stores_cents_as_long(self):
        m = Money(1050)
        eq_(m.cents, 1050)
        self.assertTrue(isinstance(m.cents, long))

    @raises(TypeError)
    def test_rejects_floats(self):
        Money(10.5)

    def test_decimal_is_rounded_half_up(self):
        eq_(Money(Decimal('10.5')).cents, 11)
        eq_(Money(Decimal('10.4')).cents, 10)

    def test_from_string(self):
        eq_(Money.from_string('12.34').cents, 1234)
        eq_(Money.from_string(u'$1,234.50').cents, 123450)
        eq_(Money.from_string('  7 ').cents, 700)
        eq_(Money.from_string('').cents, 0)
        eq_(Money.from_string(None).cents, 0)
        eq_(Money.from_string(Decimal('3.105')).cents, 311)

    @raises(ValueError)
    def test_from_string_rejects_garbage(self):
        Money.from_string('twelve dollars')

    def test_coerce(self):
        m = Money(5)
        self.assertTrue(Money.coerce(m) is m)
        eq_(Money.coerce(250).cents, 250)
        eq_(Money.coerce(250L).cents, 250)
        eq_(Money.coerce('2.50').cents, 250)
        eq_(Money.coerce(Decimal('2.50')).cents, 250)

    def test_add_and_subtract(self):
        eq_(Money(100) + Money(250), Money(350))
        eq_(Money(100) - Money(250), Money(-150))
        eq_(Money(100) + 5, Money(105))
        eq_(10 - Money(4), Money(6))

    def test_sum(self):
        eq_(sum([Money(1), Money(2), Money(3)]), Money(6))
        eq_(sum([], Money(0)), Money(0))

    @raises(TypeError)
    def test_cannot_add_string(self):
        Money(100) + '1.00'

    def test_multiply(self):
        eq_(Money(250) * 4, Money(1000))
        eq_(3 * Money(250), Money(750))
        eq_(Money(10000) * Decimal('0.0825'), Money(825))
        eq_(Money(999) * Decimal('0.0825'), Money(82))  # 82.4175

    @raises(TypeError)
    def test_cannot_multiply_money_by_money(self):
        Money(2) * Money(3)

    def test_divide_never_produces_fractional_cents(self):
        eq_(Money(1000) / 3, Money(333))
        eq_((Money(1000) / 3).cents, 333)
        self.assertTrue(isinstance((Money(1001) / 2).cents, long))

    def test_comparisons(self):
        self.assertTrue(Money(5) < Money(6))
        self.assertTrue(Money(6) >= Money(6))
        self.assertTrue(Money(5) == 5)
        self.assertTrue(Money(5) != Money(4))
        self.assertTrue(Money(5) > None)

    def test_sorting(self):
        values = [Money(30), Money(-5), Money(10)]
        eq_(sorted(values), [Money(-5), Money(10), Money(30)])

    def test_truthiness(self):
        self.assertFalse(Money(0))
        self.assertTrue(Money(1))
        self.assertTrue(Money(-1))

    def test_hashable(self):
        eq_(len(set([Money(5), Money(5), Money(6)])), 2)

    def test_negation_and_abs(self):
        eq_(-Money(5), Money(-5))
        eq_(abs(Money(-5)), Money(5))

    def test_unicode_formatting(self):
        eq_(unicode(Money(0)), u'$0.00')
        eq_(unicode(Money(5)), u'$0.05')
        eq_(unicode(Money(123456789)), u'$1,234,567.89')
        eq_(unicode(Money(-1999)), u'-$19.99')

    def test_str_is_bytes(self):
        s = str(Money(1999))
        eq_(s, '$19.99')
        self.assertTrue(isinstance(s, str))

    def test_repr(self):
        eq_(repr(Money(42)), 'Money(42)')

    def test_as_decimal(self):
        eq_(Money(1999).as_decimal(), Decimal('19.99'))
