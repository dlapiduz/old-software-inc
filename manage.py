#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
OrderDesk management script.

    python manage.py runserver            # dev server on :5000
    python manage.py seed                 # create tables + demo data
    python manage.py -c production initdb
"""
import getpass
import os
import sys

from flask.ext.script import Manager, Shell

from orderdesk import create_app
from orderdesk.extensions import db
from orderdesk import models

manager = Manager(create_app)
manager.add_option('-c', '--config', dest='config_name', required=False,
                   default=os.environ.get('ORDERDESK_ENV', 'development'))


def _make_shell_context():
    return dict(app=manager.app, db=db, models=models,
                User=models.User, Customer=models.Customer, Product=models.Product,
                Order=models.Order)

manager.add_command('shell', Shell(make_context=_make_shell_context))


@manager.command
def initdb():
    """Create all database tables."""
    db.create_all()
    print 'Created tables in %s' % db.engine.url


@manager.command
def dropdb():
    """Drop all database tables."""
    if raw_input('This will delete ALL data. Type "yes" to continue: ') != 'yes':
        print 'Aborted.'
        return
    db.drop_all()
    print 'Dropped all tables.'


@manager.option('--if-empty', dest='if_empty', action='store_true', default=False,
                help='Only seed when there are no users yet')
def seed(if_empty=False):
    """Create tables and load demo data."""
    from orderdesk.seed import load_demo_data
    db.create_all()
    if if_empty and models.User.query.count():
        print 'Database already has data, not seeding.'
        return
    load_demo_data()
    print 'Demo data loaded.'
    print 'Log in as admin/admin123, clerk/clerk123 or viewer/viewer123.'
    for user in models.User.query.order_by(models.User.id):
        print '  API token for %-8s %s' % (user.username + ':', user.api_token)


@manager.command
def createuser():
    """Interactively create a user."""
    from orderdesk.security import generate_token
    username = raw_input('Username: ').strip()
    if models.User.query.filter_by(username=username).first():
        print >> sys.stderr, 'User %s already exists' % username
        sys.exit(1)
    email = raw_input('Email: ').strip()
    role = raw_input('Role [admin/clerk/viewer] (clerk): ').strip() or 'clerk'
    if role not in models.USER_ROLES:
        print >> sys.stderr, 'Unknown role %s' % role
        sys.exit(1)
    password = getpass.getpass('Password: ')
    if password != getpass.getpass('Password (again): '):
        print >> sys.stderr, 'Passwords do not match'
        sys.exit(1)
    user = models.User(username=username, email=email, role=role, api_token=generate_token())
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print 'Created %s (%s). API token: %s' % (username, role, user.api_token)


@manager.command
def test():
    """Run the test suite."""
    import nose
    os.environ['ORDERDESK_ENV'] = 'testing'
    sys.exit(0 if nose.run(argv=['nosetests', '-v', 'tests']) else 1)


if __name__ == '__main__':
    manager.run()
