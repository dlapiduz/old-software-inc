# -*- coding: utf-8 -*-
"""
Demo data for development and training. Deterministic (seeded RNG).
"""
import random
from datetime import date, datetime, timedelta

import workflow
from extensions import db
from models import Customer, Product, PromoCode, User
from security import generate_token

USERS = [
    # username, password, role
    ('admin', 'admin123', 'admin'),
    ('clerk', 'clerk123', 'clerk'),
    ('viewer', 'viewer123', 'viewer'),
]

CUSTOMERS = [
    # name, tier, tax_exempt, credit limit (cents)
    (u'Acme Industrial Supply', 'gold', False, 5000000),
    (u'Bluebonnet Manufacturing', 'silver', False, 2500000),
    (u'Café Müller GmbH', 'standard', False, 0),
    (u'Dallas ISD Facilities', 'platinum', True, 0),
    (u'Eagle Pass Fabrication', 'standard', False, 500000),
    (u'Fort Worth Hydraulics', 'silver', False, 1500000),
    (u'Gulf Coast Marine Repair', 'gold', False, 3000000),
    (u'Hill Country Brewing Co.', 'standard', False, 250000),
    (u'Industrias Peñasco S.A.', 'silver', False, 1000000),
    (u'Joliet Tool & Die', 'standard', False, 0),
    (u'Knoxville Packaging', 'gold', False, 2000000),
    (u'Lone Star Pipe Works', 'platinum', False, 10000000),
    (u'Société Générale d\'Usinage', 'standard', False, 0),
    (u'Travis County Water Dept.', 'gold', True, 0),
]

PRODUCTS = [
    # sku, name, price (cents), stock
    ('WID-1001', u'Standard Widget, 10mm', 125, 5000),
    ('WID-1002', u'Standard Widget, 20mm', 165, 3200),
    ('WID-1003', u'Heavy Widget, 20mm', 340, 900),
    ('GSK-2001', u'Nitrile Gasket 2"', 210, 1500),
    ('GSK-2002', u'Nitrile Gasket 4"', 395, 800),
    ('GSK-2003', u'PTFE Gasket 4"', 1250, 120),
    ('FLG-3001', u'Weld Neck Flange 2" 150#', 4400, 60),
    ('FLG-3002', u'Weld Neck Flange 4" 150#', 7850, 35),
    ('FLG-3003', u'Blind Flange 4" 300#', 9900, 8),
    ('SPR-4001', u'Roller Chain Sprocket 40B12', 1875, 200),
    ('SPR-4002', u'Roller Chain Sprocket 50B18', 3120, 75),
    ('CHN-5001', u'#40 Roller Chain, 10ft', 2995, 140),
    ('CHN-5002', u'#50 Roller Chain, 10ft', 4250, 10),
    ('BRG-6001', u'Pillow Block Bearing 1"', 2150, 300),
    ('BRG-6002', u'Pillow Block Bearing 1-1/2"', 3475, 4),
    ('VLV-7001', u'Ball Valve 1" NPT Brass', 2399, 250),
    ('VLV-7002', u'Ball Valve 2" NPT Stainless', 11950, 40),
    ('VLV-7003', u'Check Valve 2" Bronze', 8900, 22),
    ('HOS-8001', u'Hydraulic Hose 1/2" x 25ft', 6450, 55),
    ('HOS-8002', u'Hydraulic Hose 3/4" x 25ft', 8875, 12),
    ('FST-9001', u'Hex Bolt 1/2-13 x 2" (box of 50)', 1899, 600),
    ('FST-9002', u'Hex Nut 1/2-13 (box of 100)', 1150, 700),
    ('FST-9003', u'Flat Washer 1/2" (box of 100)', 675, 10),
]

PROMOS = [
    # code, percent off, min subtotal (cents), expires in days (None = never), active
    ('SPRING14', 12, 0, 30, True),
    ('BIGBUY', 20, 250000, None, True),
    ('WELCOME5', 5, 0, None, True),
    ('XMAS13', 25, 0, -300, True),
    ('PARTNER', 30, 0, None, False),
]


def load_demo_data(rng=None):
    rng = rng or random.Random(1404)
    today = date.today()

    users = {}
    for username, password, role in USERS:
        user = User(username=username, email='%s@oldsoftware.example' % username,
                    role=role, api_token=generate_token())
        user.set_password(password)
        db.session.add(user)
        users[username] = user

    customers = []
    for name, tier, exempt, limit in CUSTOMERS:
        customer = Customer(account_number=Customer.next_account_number(), name=name,
                            tier=tier, tax_exempt=exempt, credit_limit_cents=limit,
                            email='purchasing@%s.example' % name.split()[0].lower().encode('ascii', 'ignore'))
        db.session.add(customer)
        db.session.flush()
        customers.append(customer)

    products = []
    for sku, name, price, stock in PRODUCTS:
        product = Product(sku=sku, name=name, price_cents=price, stock=stock)
        db.session.add(product)
        products.append(product)
    discontinued = Product(sku='WID-0999', name=u'Legacy Widget (old spec)', price_cents=99,
                           stock=0, discontinued=True)
    db.session.add(discontinued)

    for code, pct, minimum, days, active in PROMOS:
        expires = None
        if days is not None:
            expires = today + timedelta(days=days)
        db.session.add(PromoCode(code=code, percent_off=pct, min_subtotal_cents=minimum,
                                 expires_on=expires, active=active))
    db.session.flush()

    admin, clerk = users['admin'], users['clerk']
    final_states = ['draft', 'submitted', 'approved', 'shipped', 'invoiced', 'invoiced',
                    'invoiced', 'shipped', 'cancelled']
    for i in xrange(60):
        customer = rng.choice(customers)
        order = workflow.create_order(customer, clerk)
        for product in rng.sample(products, rng.randint(1, 4)):
            qty = rng.choice([1, 2, 5, 10, 12, 25, 50, 100, 150])
            qty = min(qty, max(1, product.available / 4))
            workflow.add_line(order, product, qty, clerk)
        if rng.random() < 0.15:
            try:
                workflow.apply_promo(order, rng.choice(['SPRING14', 'WELCOME5', 'BIGBUY']), clerk)
            except workflow.WorkflowError:
                pass

        target = rng.choice(final_states)
        try:
            if target != 'draft':
                if target == 'cancelled':
                    workflow.cancel_order(order, clerk, u'Customer changed their mind')
                else:
                    workflow.submit_order(order, clerk)
                    if target in ('approved', 'shipped', 'invoiced'):
                        workflow.approve_order(order, admin)
                    if target in ('shipped', 'invoiced'):
                        workflow.ship_order(order, clerk)
                    if target == 'invoiced':
                        workflow.invoice_order(order, admin)
        except workflow.WorkflowError, e:
            print '  seed: %s stays %s (%s)' % (order.number, order.status, e)

        order.created_at = datetime.utcnow() - timedelta(days=rng.randint(0, 75),
                                                         hours=rng.randint(0, 23))
        db.session.flush()

    db.session.commit()
