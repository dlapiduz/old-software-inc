# -*- coding: utf-8 -*-
from datetime import date, datetime

from extensions import db
from money import Money
from security import hash_password

ORDER_STATUSES = ('draft', 'submitted', 'approved', 'shipped', 'invoiced', 'cancelled')
OPEN_STATUSES = ('submitted', 'approved', 'shipped')
CUSTOMER_TIERS = ('standard', 'silver', 'gold', 'platinum')
USER_ROLES = ('admin', 'clerk', 'viewer')


def _iso(value):
    if value is None:
        return None
    return value.isoformat()


class MoneyProperty(object):
    """Exposes an integer ``*_cents`` column as a Money object."""

    def __init__(self, column_name):
        self.column_name = column_name

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        return Money(getattr(obj, self.column_name) or 0)

    def __set__(self, obj, value):
        setattr(obj, self.column_name, Money.coerce(value).cents)


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(16), nullable=False, default='clerk')
    api_token = db.Column(db.String(40), unique=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = hash_password(password)

    # Flask-Login interface
    def is_authenticated(self):
        return True

    def is_active(self):
        return self.active

    def is_anonymous(self):
        return False

    def get_id(self):
        return unicode(self.id)

    def is_admin(self):
        return self.role == 'admin'

    def can_edit(self):
        return self.role in ('admin', 'clerk')

    def __unicode__(self):
        return self.username

    def __repr__(self):
        return '<User %r>' % self.username


class Customer(db.Model):
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    account_number = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.Unicode(200), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(40))
    tier = db.Column(db.String(16), nullable=False, default='standard')
    tax_exempt = db.Column(db.Boolean, nullable=False, default=False)
    # 0 means no limit
    credit_limit_cents = db.Column(db.Integer, nullable=False, default=0)
    notes = db.Column(db.UnicodeText)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='customer', lazy='dynamic')

    credit_limit = MoneyProperty('credit_limit_cents')

    @classmethod
    def next_account_number(cls):
        last = db.session.query(db.func.max(cls.id)).scalar() or 0
        return 'C-%05d' % (last + 1)

    def open_balance(self):
        total = 0
        for order in self.orders.filter(Order.status.in_(OPEN_STATUSES)):
            total += order.total_cents
        return Money(total)

    def to_dict(self):
        return {
            'account_number': self.account_number,
            'name': self.name,
            'email': self.email,
            'phone': self.phone,
            'tier': self.tier,
            'tax_exempt': self.tax_exempt,
            'credit_limit_cents': self.credit_limit_cents,
        }

    def __unicode__(self):
        return u'%s %s' % (self.account_number, self.name)

    def __repr__(self):
        return '<Customer %s>' % self.account_number


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(32), unique=True, nullable=False)
    name = db.Column(db.Unicode(200), nullable=False)
    description = db.Column(db.UnicodeText)
    price_cents = db.Column(db.Integer, nullable=False, default=0)
    stock = db.Column(db.Integer, nullable=False, default=0)
    reserved = db.Column(db.Integer, nullable=False, default=0)
    discontinued = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    price = MoneyProperty('price_cents')

    @property
    def available(self):
        return (self.stock or 0) - (self.reserved or 0)

    def to_dict(self):
        return {
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'price_cents': self.price_cents,
            'price': unicode(self.price),
            'stock': self.stock,
            'reserved': self.reserved,
            'available': self.available,
            'discontinued': self.discontinued,
        }

    def __unicode__(self):
        return u'%s %s' % (self.sku, self.name)

    def __repr__(self):
        return '<Product %s>' % self.sku


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False)
    percent_off = db.Column(db.Integer, nullable=False)
    min_subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    expires_on = db.Column(db.Date)
    active = db.Column(db.Boolean, nullable=False, default=True)

    min_subtotal = MoneyProperty('min_subtotal_cents')

    def is_valid(self, subtotal, today=None):
        if today is None:
            today = date.today()
        if not self.active:
            return False
        if self.expires_on is not None and self.expires_on < today:
            return False
        return subtotal >= self.min_subtotal

    def __repr__(self):
        return '<PromoCode %s>' % self.code


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(16), unique=True, nullable=False)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=False)
    status = db.Column(db.String(16), nullable=False, default='draft')
    promo_code = db.Column(db.String(32))
    notes = db.Column(db.UnicodeText)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submitted_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    invoiced_at = db.Column(db.DateTime)

    subtotal_cents = db.Column(db.Integer, nullable=False, default=0)
    line_discount_cents = db.Column(db.Integer, nullable=False, default=0)
    discount_cents = db.Column(db.Integer, nullable=False, default=0)
    discount_reason = db.Column(db.String(64))
    tax_cents = db.Column(db.Integer, nullable=False, default=0)
    shipping_cents = db.Column(db.Integer, nullable=False, default=0)
    total_cents = db.Column(db.Integer, nullable=False, default=0)

    lines = db.relationship('OrderLine', backref='order', cascade='all, delete-orphan',
                            order_by='OrderLine.id')
    created_by = db.relationship('User')

    subtotal = MoneyProperty('subtotal_cents')
    line_discount = MoneyProperty('line_discount_cents')
    discount = MoneyProperty('discount_cents')
    tax = MoneyProperty('tax_cents')
    shipping = MoneyProperty('shipping_cents')
    total = MoneyProperty('total_cents')

    @classmethod
    def next_number(cls):
        last = db.session.query(db.func.max(cls.id)).scalar() or 0
        return 'SO-%06d' % (last + 1)

    @property
    def is_editable(self):
        return self.status == 'draft'

    def recalculate(self, tax_rate=None):
        from pricing import price_order
        quote = price_order(self, tax_rate=tax_rate)
        self.subtotal = quote.subtotal
        self.line_discount = quote.line_discounts
        self.discount = quote.discount
        self.discount_reason = quote.discount_reason
        self.tax = quote.tax
        self.shipping = quote.shipping
        self.total = quote.total
        return quote

    def allowed_actions(self):
        from workflow import TRANSITIONS, ACTION_FOR_STATUS
        return [ACTION_FOR_STATUS[s] for s in TRANSITIONS.get(self.status, ())]

    def to_dict(self, include_lines=True):
        data = {
            'number': self.number,
            'customer': self.customer.account_number,
            'customer_name': self.customer.name,
            'status': self.status,
            'promo_code': self.promo_code,
            'notes': self.notes,
            'created_at': _iso(self.created_at),
            'submitted_at': _iso(self.submitted_at),
            'shipped_at': _iso(self.shipped_at),
            'invoiced_at': _iso(self.invoiced_at),
            'subtotal_cents': self.subtotal_cents,
            'line_discount_cents': self.line_discount_cents,
            'discount_cents': self.discount_cents,
            'discount_reason': self.discount_reason,
            'tax_cents': self.tax_cents,
            'shipping_cents': self.shipping_cents,
            'total_cents': self.total_cents,
            'total': unicode(self.total),
        }
        if include_lines:
            data['lines'] = [line.to_dict() for line in self.lines]
        return data

    def __repr__(self):
        return '<Order %s %s>' % (self.number, self.status)


class OrderLine(db.Model):
    __tablename__ = 'order_lines'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price_cents = db.Column(db.Integer, nullable=False)
    discount_cents = db.Column(db.Integer, nullable=False, default=0)

    product = db.relationship('Product')

    unit_price = MoneyProperty('unit_price_cents')
    discount = MoneyProperty('discount_cents')

    @property
    def gross(self):
        return self.unit_price * self.quantity

    @property
    def total(self):
        return self.gross - self.discount

    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.product.sku,
            'name': self.product.name,
            'quantity': self.quantity,
            'unit_price_cents': self.unit_price_cents,
            'discount_cents': self.discount_cents,
            'total_cents': self.total.cents,
        }


class AuditEntry(db.Model):
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(64), nullable=False)
    object_type = db.Column(db.String(32), nullable=False)
    object_id = db.Column(db.Integer)
    detail = db.Column(db.UnicodeText)

    user = db.relationship('User')


class ReportCache(db.Model):
    __tablename__ = 'report_cache'

    key = db.Column(db.String(128), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    payload = db.Column(db.LargeBinary)
