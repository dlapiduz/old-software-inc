# -*- coding: utf-8 -*-
"""
Money type used throughout OrderDesk.

All amounts are kept as integer cents (``long``) so we never get float
rounding problems on invoices. Do NOT pass floats in here (see OD-112).
"""
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

CENT = Decimal('1')


def _round(d):
    return long(d.quantize(CENT, rounding=ROUND_HALF_UP))


class Money(object):

    def __init__(self, cents=0):
        if isinstance(cents, float):
            raise TypeError('Money does not accept floats (got %r)' % cents)
        if isinstance(cents, Decimal):
            cents = _round(cents)
        self.cents = long(cents)

    @classmethod
    def from_string(cls, value):
        """Parse a dollar amount like ``"$1,234.50"`` or ``Decimal('3.10')``."""
        if value is None:
            return cls(0)
        if isinstance(value, Decimal):
            d = value
        else:
            value = unicode(value).strip().replace(u',', u'').replace(u'$', u'')
            if not value:
                return cls(0)
            try:
                d = Decimal(value)
            except InvalidOperation:
                raise ValueError('Not a money amount: %r' % value)
        return cls(_round(d * 100))

    @classmethod
    def coerce(cls, value):
        """Ints/longs are treated as cents, everything else as dollars."""
        if isinstance(value, Money):
            return value
        if isinstance(value, (int, long)):
            return cls(value)
        return cls.from_string(value)

    def as_decimal(self):
        return Decimal(self.cents) / 100

    def _other(self, other):
        if isinstance(other, Money):
            return other.cents
        if isinstance(other, (int, long)):
            return other
        raise TypeError('Cannot combine Money with %s' % type(other).__name__)

    def __add__(self, other):
        return Money(self.cents + self._other(other))

    # lets sum() work, since it starts from 0
    __radd__ = __add__

    def __sub__(self, other):
        return Money(self.cents - self._other(other))

    def __rsub__(self, other):
        return Money(self._other(other) - self.cents)

    def __mul__(self, factor):
        if isinstance(factor, Money):
            raise TypeError('Cannot multiply Money by Money')
        if isinstance(factor, (int, long)):
            return Money(self.cents * factor)
        return Money(Decimal(self.cents) * Decimal(str(factor)))

    __rmul__ = __mul__

    def __div__(self, divisor):
        if isinstance(divisor, Money):
            raise TypeError('Cannot divide Money by Money')
        # integer division on purpose, we never want fractional cents
        return Money(self.cents / divisor)

    def __neg__(self):
        return Money(-self.cents)

    def __abs__(self):
        return Money(abs(self.cents))

    def __cmp__(self, other):
        if other is None:
            return 1
        return cmp(self.cents, self._other(other))

    def __hash__(self):
        return hash(self.cents)

    def __nonzero__(self):
        return self.cents != 0

    def __unicode__(self):
        sign = u'-' if self.cents < 0 else u''
        dollars, cents = divmod(abs(self.cents), 100)
        return u'%s$%s.%02d' % (sign, u'{:,}'.format(dollars), cents)

    def __str__(self):
        return unicode(self).encode('utf-8')

    def __repr__(self):
        return 'Money(%d)' % self.cents
