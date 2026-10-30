from nose.tools import eq_, raises

from orderdesk import inventory

from base import AppTestCase
from factories import make_product


class InventoryTest(AppTestCase):

    def test_reserve(self):
        product = make_product(stock=50)
        inventory.reserve(product, 20)
        eq_(product.reserved, 20)
        eq_(product.available, 30)
        eq_(product.stock, 50)

    def test_reserve_too_much(self):
        product = make_product(sku='TIGHT-1', stock=5, reserved=3)
        try:
            inventory.reserve(product, 3)
        except inventory.InsufficientStock, e:
            eq_(e.product, product)
            eq_(e.requested, 3)
            eq_(str(e), 'Insufficient stock for TIGHT-1: requested 3, available 2')
        else:
            self.fail('expected InsufficientStock')
        eq_(product.reserved, 3)

    @raises(ValueError)
    def test_reserve_requires_positive_quantity(self):
        inventory.reserve(make_product(), 0)

    def test_release(self):
        product = make_product(stock=50, reserved=10)
        inventory.release(product, 4)
        eq_(product.reserved, 6)

    def test_release_never_goes_negative(self):
        product = make_product(stock=50, reserved=2)
        inventory.release(product, 10)
        eq_(product.reserved, 0)

    def test_commit(self):
        product = make_product(stock=50, reserved=10)
        inventory.commit(product, 10)
        eq_(product.stock, 40)
        eq_(product.reserved, 0)
        eq_(product.available, 40)

    def test_low_stock(self):
        low = make_product(sku='LOW', stock=3)
        reserved = make_product(sku='RES', stock=40, reserved=35)
        make_product(sku='PLENTY', stock=50)
        make_product(sku='GONE', stock=0, discontinued=True)
        eq_(inventory.low_stock_products(), [low, reserved])

    def test_low_stock_custom_threshold(self):
        product = make_product(sku='MID', stock=40)
        eq_(inventory.low_stock_products(threshold=50), [product])
        eq_(inventory.low_stock_products(threshold=5), [])
