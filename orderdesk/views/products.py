from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask.ext.login import current_user, login_required

from orderdesk import audit
from orderdesk.decorators import admin_required
from orderdesk.extensions import db
from orderdesk.forms import ProductForm
from orderdesk.models import Product
from orderdesk.utils import paginate

bp = Blueprint('products', __name__)


def _apply_form(form, product):
    product.sku = form.sku.data.strip().upper()
    product.name = form.name.data.strip()
    product.description = form.description.data or None
    product.price = form.price_amount.data
    product.stock = form.stock.data or 0
    product.discontinued = form.discontinued.data


def _sku_taken(sku, product=None):
    existing = Product.query.filter_by(sku=sku.strip().upper()).first()
    return existing is not None and existing is not product


@bp.route('/products')
@login_required
def index():
    query = Product.query
    if request.args.get('show') != 'all':
        query = query.filter_by(discontinued=False)
    page = paginate(query.order_by(Product.sku), request.args.get('page', 1, type=int))
    return render_template('products/index.html', page=page, show=request.args.get('show'))


@bp.route('/products/new', methods=['GET', 'POST'])
@admin_required
def create():
    form = ProductForm()
    if form.validate_on_submit():
        if _sku_taken(form.sku.data):
            form.sku.errors.append(u'SKU already exists')
        else:
            product = Product()
            _apply_form(form, product)
            db.session.add(product)
            db.session.flush()
            audit.record(current_user, 'create', 'product', product.id, product.sku)
            db.session.commit()
            flash(u'Product %s created.' % product.sku, 'success')
            return redirect(url_for('.index'))
    return render_template('products/form.html', form=form, product=None)


@bp.route('/products/<int:product_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(product_id):
    product = Product.query.get_or_404(product_id)
    form = ProductForm(obj=product)
    if request.method == 'GET':
        form.price_amount.data = product.price.as_decimal()
    if form.validate_on_submit():
        if _sku_taken(form.sku.data, product):
            form.sku.errors.append(u'SKU already exists')
        else:
            _apply_form(form, product)
            audit.record(current_user, 'update', 'product', product.id, product.sku)
            db.session.commit()
            flash(u'Product %s updated.' % product.sku, 'success')
            return redirect(url_for('.index'))
    return render_template('products/form.html', form=form, product=product)
