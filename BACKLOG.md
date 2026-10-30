# OrderDesk backlog

Exported from the tracker. Each ticket describes symptoms as reported.

## Bugs

### OD-201: Customers are overcharged tax when a discount applies
Reported by accounting. Gold customer Acme ordered $1,000.00 of widgets, got
their 10% tier discount, and was charged $82.50 tax. Accounting says it should
be $74.25. Orders without a discount look right.

### OD-207: Reserved stock never comes back for some cancelled orders
The warehouse says the "Reserved" column for FLG-3002 keeps growing even
though nobody has open orders for it. Probably related to orders cancelled
after an admin approved them.

### OD-214: Low stock list on the dashboard misses items
Products with exactly 10 units available don't show on the dashboard. Ops
expects anything at or below the threshold in `config.py` to be listed.

### OD-219: Sales report total doesn't match accounting for the month
Run the report for 2014-03-01 to 2014-03-31 and orders created on March 31
are missing. Users expect both dates to be included.

### OD-223: Can't reach the last products in the catalog
With the demo data the products list says "Page 1 of 1" but some SKUs
(e.g. WID-1003) never show up. The same thing happens on customers and orders
once there are more than 20.

### OD-226: Sales report sometimes shows yesterday's numbers
The report is cached for 5 minutes. Sometimes it shows numbers that are
more than a day old.

### OD-230: 500 error when logging in with an accented password
A user in the Monterrey office set the password `contraseña` with
`manage.py createuser` and gets an Internal Server Error when logging in.

### OD-232: Customer search misses accented names
Searching for `café` finds "Café Müller GmbH", but `CAFÉ` does not. `acme`
and `ACME` both work.

## Security

### OD-235: Login redirects to any URL in `next`
`/login?next=http://evil.example` sends the user offsite after they log in.

### OD-236: Order action buttons have no CSRF protection
The submit/approve/ship/cancel and remove-line forms are plain POSTs with no
CSRF token.

### OD-237: Passwords are stored as salted SHA-1
Security audit finding. Move to a modern KDF. Existing users must not have
to reset their passwords.

## Tech debt / platform

### OD-301: Python 2.7 is end of life
Infra won't patch the 2.7 base image any more. We need a path to Python 3.

### OD-302: Upgrade Flask and extensions
Flask 0.10, Flask-Login 0.2, Flask-WTF 0.10, Flask-SQLAlchemy 1.0 and
WTForms 2.0 are all years out of date.

### OD-303: Upgrade SQLAlchemy
We're on 0.9.8.

### OD-304: Replace Flask-Script
Flask-Script is unmaintained. Move `manage.py` commands to the `flask` CLI.

### OD-305: Replace nose
nose is unmaintained. Move the suite to pytest without losing coverage.

### OD-306: Database migrations
The schema is created with `db.create_all()`. There is no way to change it
on an existing database. Add Alembic.

### OD-307: Order and account numbers can collide
Numbers are made from `max(id) + 1`. Two clerks creating orders at the same
time have produced duplicate `SO-` numbers, which fail with an IntegrityError.

### OD-308: Webhooks block the request
`notifications.notify` calls urllib2 inline with a 5 second timeout. When the
WMS is down every order action takes 5+ seconds.
