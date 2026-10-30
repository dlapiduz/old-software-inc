from flask import current_app

from models import Product


class InsufficientStock(Exception):

    def __init__(self, product, requested):
        Exception.__init__(self, 'Insufficient stock for %s: requested %d, available %d'
                           % (product.sku, requested, product.available))
        self.product = product
        self.requested = requested


def reserve(product, quantity):
    if quantity <= 0:
        raise ValueError('quantity must be positive')
    if product.available < quantity:
        raise InsufficientStock(product, quantity)
    product.reserved += quantity


def release(product, quantity):
    product.reserved = max(0, product.reserved - quantity)


def commit(product, quantity):
    """Stock physically left the warehouse."""
    product.stock -= quantity
    product.reserved = max(0, product.reserved - quantity)


def low_stock_products(threshold=None):
    if threshold is None:
        threshold = current_app.config['LOW_STOCK_THRESHOLD']
    products = Product.query.filter_by(discontinued=False).order_by(Product.sku).all()
    return [p for p in products if p.available < threshold]
