# -*- coding: utf-8 -*-
"""
OrderDesk - order management for Old Software Inc.
"""
import logging
import os
from datetime import datetime

from flask import Flask, render_template

from config import config as config_map
from extensions import db, login_manager
from money import Money

__version__ = '1.4.2'


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('ORDERDESK_ENV', 'default')
    app = Flask(__name__)
    app.config.from_object(config_map[config_name])

    db.init_app(app)
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    _register_blueprints(app)
    _register_template_helpers(app)
    _register_error_handlers(app)

    if not app.debug and not app.testing:
        logging.basicConfig(level=logging.INFO)
    return app


def _register_blueprints(app):
    from views import api, auth, customers, main, orders, products, reports
    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(customers.bp)
    app.register_blueprint(products.bp)
    app.register_blueprint(orders.bp)
    app.register_blueprint(reports.bp)
    app.register_blueprint(api.bp, url_prefix='/api/v1')


def _register_template_helpers(app):

    @app.template_filter('money')
    def money_filter(value):
        if not isinstance(value, Money):
            value = Money(value or 0)
        return unicode(value)

    @app.template_filter('dt')
    def datetime_filter(value, fmt='%Y-%m-%d %H:%M'):
        if value is None:
            return u''
        return value.strftime(fmt)

    @app.context_processor
    def inject_globals():
        return {
            'company_name': app.config['COMPANY_NAME'],
            'version': __version__,
            'year': datetime.utcnow().year,
        }


def _register_error_handlers(app):

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404
