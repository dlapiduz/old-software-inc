# -*- coding: utf-8 -*-
"""
OrderDesk configuration.

Pick a config with ORDERDESK_ENV (development, testing, production) or
``python manage.py -c <name> ...``.
"""
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config(object):
    SECRET_KEY = os.environ.get('ORDERDESK_SECRET', 'osi-orderdesk-2011-changeme')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'ORDERDESK_DB', 'sqlite:///' + os.path.join(basedir, 'orderdesk.db'))
    SQLALCHEMY_ECHO = False
    WTF_CSRF_ENABLED = True

    COMPANY_NAME = u'Old Software Inc.'
    ITEMS_PER_PAGE = 20

    # Texas sales tax, applied to the order after discounts.
    TAX_RATE = '0.0825'

    # Products with this many units available *or fewer* show up on the
    # dashboard low stock list.
    LOW_STOCK_THRESHOLD = 10

    # Order events are POSTed here as JSON. Leave unset to disable.
    WEBHOOK_URL = os.environ.get('ORDERDESK_WEBHOOK')
    WEBHOOK_TIMEOUT = 5

    REPORT_CACHE_SECONDS = 300


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    # Flask-Login 0.2 turns @login_required off when TESTING is set
    LOGIN_DISABLED = False
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False
    WEBHOOK_URL = None
    REPORT_CACHE_SECONDS = 0


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
