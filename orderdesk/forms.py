from flask.ext.wtf import Form
from wtforms import (BooleanField, DecimalField, IntegerField, PasswordField,
                     SelectField, TextAreaField, TextField)
from wtforms.validators import Email, Length, NumberRange, Optional, Required

from models import CUSTOMER_TIERS


class LoginForm(Form):
    username = TextField('Username', validators=[Required()])
    password = PasswordField('Password', validators=[Required()])
    remember = BooleanField('Remember me')


class CustomerForm(Form):
    name = TextField('Name', validators=[Required(), Length(max=200)])
    email = TextField('Email', validators=[Optional(), Email()])
    phone = TextField('Phone', validators=[Optional(), Length(max=40)])
    tier = SelectField('Tier', choices=[(t, t.title()) for t in CUSTOMER_TIERS],
                       default='standard')
    tax_exempt = BooleanField('Tax exempt')
    credit_limit_amount = DecimalField('Credit limit ($, blank for none)', places=2,
                                       validators=[Optional(), NumberRange(min=0)])
    notes = TextAreaField('Notes')


class ProductForm(Form):
    sku = TextField('SKU', validators=[Required(), Length(max=32)])
    name = TextField('Name', validators=[Required(), Length(max=200)])
    description = TextAreaField('Description')
    price_amount = DecimalField('Price ($)', places=2,
                                validators=[Required(), NumberRange(min=0)])
    stock = IntegerField('Stock on hand', default=0, validators=[NumberRange(min=0)])
    discontinued = BooleanField('Discontinued')


class NewOrderForm(Form):
    customer_id = SelectField('Customer', coerce=int)
    notes = TextAreaField('Notes')


class OrderLineForm(Form):
    product_id = SelectField('Product', coerce=int)
    quantity = IntegerField('Quantity', default=1, validators=[Required(), NumberRange(min=1)])


class PromoForm(Form):
    code = TextField('Promo code', validators=[Optional(), Length(max=32)])
