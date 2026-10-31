#!/usr/bin/env python3
"""
Create the OrderDesk backlog as GitHub issues.

This is repo tooling, not part of the app, so it runs on the host's Python 3
(stdlib only) and talks to GitHub through the `gh` CLI. Run `gh auth login`
first.

    scripts/create_issues.py --dry-run           # show what would be created
    scripts/create_issues.py                     # create labels + issues
    scripts/create_issues.py --repo me/fork      # another repo
    scripts/create_issues.py --only OD-201,OD-404

It is safe to re-run: an issue is skipped when one with the same ticket
prefix ("OD-201:") already exists, open or closed. To start over, delete the
issues (or the repo) and run it again.

Issue bodies describe symptoms and acceptance criteria only, never the
root cause, so they can be handed to an agent as-is.
"""
import argparse
import json
import subprocess
import sys

LABELS = {
    'bug': ('d73a4a', 'Something is not working'),
    'security': ('b60205', 'Security weakness'),
    'feature': ('0e8a16', 'New functionality'),
    'tech-debt': ('fbca04', 'Upgrades, migrations and cleanup'),
    'size: small': ('c2e0c6', 'An hour or two, touches one or two files'),
    'size: medium': ('7fc8a0', 'A day or so, touches several modules'),
    'size: large': ('2d7a50', 'Multi-day, cross-cutting change'),
    'good first issue': ('7057ff', 'Small and self-contained'),
    # policy waivers, see CONTRIBUTING.md
    'no-tests-needed': ('ededed', 'Maintainer waiver: PR changes code without changing tests'),
    'tests-removed-ok': ('ededed', 'Maintainer waiver: PR may reduce the number of tests'),
}

REGRESSION = '- [ ] A regression test fails before the fix and passes after it\n'
GREEN = '- [ ] `make docker-test` passes\n'


def issue(key, title, labels, body):
    return {'key': key, 'title': '%s: %s' % (key, title), 'labels': labels,
            'body': body.strip() + '\n'}


ISSUES = [
    # ---- bugs -------------------------------------------------------------
    issue('OD-201', 'Customers are overcharged tax when a discount applies',
          ['bug', 'size: small', 'good first issue'], """
Reported by accounting. Gold customer Acme ordered $1,000.00 of widgets, got
their 10% tier discount, and was charged **$82.50** tax. Accounting says it
should be **$74.25**. Orders without a discount look right.

### Acceptance criteria
- [ ] Sales tax is charged on what the customer actually pays for the goods
- [ ] Tax-exempt customers still pay no tax
""" + REGRESSION + GREEN),

    issue('OD-207', 'Reserved stock never comes back for some cancelled orders',
          ['bug', 'size: small'], """
The warehouse says the "Reserved" column for FLG-3002 keeps growing even
though nobody has open orders for it. It seems to happen with orders that
were cancelled after an admin approved them.

### Acceptance criteria
- [ ] Cancelling an order returns all of its reserved stock, whatever state it was in
- [ ] Cancelling a draft (nothing reserved) doesn't change stock
""" + REGRESSION + GREEN),

    issue('OD-214', 'Low stock list on the dashboard misses items',
          ['bug', 'size: small', 'good first issue'], """
Products with exactly 10 units available don't show on the dashboard. Ops
expects anything **at or below** `LOW_STOCK_THRESHOLD` in `config.py` to be
listed.

### Acceptance criteria
- [ ] A product with `available == LOW_STOCK_THRESHOLD` is listed
""" + REGRESSION + GREEN),

    issue('OD-219', 'Sales report total does not match accounting for the month',
          ['bug', 'size: small', 'good first issue'], """
Run the sales report for 2014-03-01 to 2014-03-31: orders created on March 31
are missing. Users expect both dates in the range to be included.

### Acceptance criteria
- [ ] Orders created at any time on the end date are included
- [ ] Orders created the day after the end date are not
""" + REGRESSION + GREEN),

    issue('OD-223', 'Cannot reach the last products in the catalog',
          ['bug', 'size: small', 'good first issue'], """
With the demo data the products list says "Page 1 of 1" but some SKUs
(e.g. WID-1003) never show up. The same thing happens on the customers and
orders lists once there are more than 20 rows.

### Acceptance criteria
- [ ] Every row is reachable through the pager on every paginated list
- [ ] An empty list still shows "Page 1 of 1"
""" + REGRESSION + GREEN),

    issue('OD-226', 'Sales report sometimes shows yesterday\'s numbers',
          ['bug', 'size: small'], """
The sales report is cached for 5 minutes (`REPORT_CACHE_SECONDS`). Sometimes
it shows numbers that are more than a day old.

### Acceptance criteria
- [ ] A cached report older than `REPORT_CACHE_SECONDS` is always rebuilt, however old it is
""" + REGRESSION + GREEN),

    issue('OD-230', '500 error when logging in with an accented password',
          ['bug', 'size: small'], """
A user in the Monterrey office set the password `contraseña` with
`manage.py createuser` and gets an Internal Server Error when logging in.

### Acceptance criteria
- [ ] Users can set and log in with non-ASCII passwords
- [ ] Existing passwords keep working
""" + REGRESSION + GREEN),

    issue('OD-232', 'Customer search misses accented names',
          ['bug', 'size: medium'], """
Searching customers for `café` finds "Café Müller GmbH", but `CAFÉ` does not.
`acme` and `ACME` both work.

### Acceptance criteria
- [ ] Customer search is case-insensitive for non-ASCII names too
- [ ] Search still works on existing databases (no manual data fix needed)
""" + REGRESSION + GREEN),

    # ---- security ---------------------------------------------------------
    issue('OD-235', 'Login redirects to any URL in `next`',
          ['security', 'size: small', 'good first issue'], """
`/login?next=http://evil.example` sends the user offsite after they log in.

### Acceptance criteria
- [ ] Only same-site paths are followed after login; anything else goes to the dashboard
- [ ] `/login?next=/orders` still works
- [ ] Tests cover absolute URLs, scheme-relative URLs (`//evil.example`) and normal paths
""" + GREEN),

    issue('OD-236', 'Order action buttons have no CSRF protection',
          ['security', 'size: medium'], """
The submit / approve / ship / invoice / cancel buttons and the remove-line form
on the order page are plain POSTs with no CSRF token, so another site can make
a logged-in user's browser change orders.

### Acceptance criteria
- [ ] Every state-changing HTML form requires a valid CSRF token
- [ ] The JSON API (token auth) keeps working without CSRF tokens
- [ ] Tests show a POST without a token is rejected
""" + GREEN),

    issue('OD-237', 'Passwords are stored as salted SHA-1',
          ['security', 'size: medium'], """
Security audit finding: password hashes are salted SHA-1. Move to a modern
password hashing scheme (bcrypt, scrypt, PBKDF2 with a high iteration count).

### Acceptance criteria
- [ ] New and changed passwords use the new scheme
- [ ] Existing users can log in without a reset, and their hash is upgraded on their next successful login
- [ ] Existing test vectors for legacy hashes still verify
""" + GREEN),

    issue('OD-238', 'Read-only users can change orders through the API',
          ['security', 'size: small'], """
In the web UI a `viewer` cannot create, ship or cancel orders. With a viewer's
API token, `POST /api/v1/orders` and `POST /api/v1/orders/<number>/ship` (and
the other actions) work anyway.

### Acceptance criteria
- [ ] The API enforces the same role rules as the web UI
- [ ] A viewer token gets `403` with a JSON error on write endpoints and can still read
""" + REGRESSION + GREEN),

    issue('OD-239', 'API tokens leak into logs via `?token=`',
          ['security', 'size: small'], """
The API accepts the token as a `?token=` query parameter as well as the
`X-OrderDesk-Token` header. Query strings end up in access logs, proxy logs
and browser history.

### Acceptance criteria
- [ ] Tokens are only accepted in the header
- [ ] The README and API docstring are updated
- [ ] A request with `?token=` gets `401` with an error that points to the header
""" + GREEN),

    issue('OD-240', 'Production starts with the built-in default secret key',
          ['security', 'size: small', 'good first issue'], """
If `ORDERDESK_SECRET` isn't set, the app quietly falls back to a hard-coded
secret key, even in production. Anyone who has read the source can forge
session cookies.

### Acceptance criteria
- [ ] The production config refuses to start without `ORDERDESK_SECRET`, with a clear error
- [ ] Development and testing keep working without it
- [ ] The Docker image docs show how to set it
""" + GREEN),

    issue('OD-241', 'No protection against password guessing',
          ['security', 'size: medium'], """
The login form accepts unlimited attempts. Nothing is logged when an attempt
fails, so nobody would notice a brute-force attempt.

### Acceptance criteria
- [ ] Failed logins are written to the audit log (username, IP)
- [ ] After N failures for a username within a window, further attempts are refused for a while (configurable)
- [ ] A successful login resets the counter
- [ ] Works with SQLite, no new infrastructure
""" + GREEN),

    issue('OD-242', 'Webhooks are not signed',
          ['security', 'size: medium'], """
The WMS can't tell whether an order event really came from OrderDesk:
webhook POSTs carry no signature, so anyone who knows the WMS URL can fake
"order shipped" events.

### Acceptance criteria
- [ ] New setting `ORDERDESK_WEBHOOK_SECRET`; when set, every webhook has an HMAC-SHA256 signature header over the raw body
- [ ] The signature includes a timestamp so old requests can't be replayed
- [ ] The README documents how a receiver verifies it
- [ ] Tests check the header against a known vector
""" + GREEN),

    issue('OD-243', 'Report cache loads pickles from the database',
          ['security', 'tech-debt', 'size: medium'], """
The sales report cache stores Python pickles in the `report_cache` table and
unpickles them on read. Anyone who can write to the database can run code in
the app. Pickles also tie the stored data to Python 2 class layouts.

### Acceptance criteria
- [ ] The cache stores a plain data format (e.g. JSON with amounts in cents)
- [ ] Existing rows in the old format are ignored or rebuilt, never unpickled
- [ ] Report output is unchanged
""" + GREEN),

    # ---- features ---------------------------------------------------------
    issue('OD-401', 'Search and filter the products list',
          ['feature', 'size: small', 'good first issue'], """
The customers list has a search box; the products list doesn't. Clerks scroll
through pages to find a SKU.

### Acceptance criteria
- [ ] Search by SKU or name (case-insensitive) on `/products`
- [ ] Filter "low stock only"
- [ ] Works together with the existing "show discontinued" toggle and pagination
- [ ] View tests for each filter
""" + GREEN),

    issue('OD-402', 'Export the product catalog as CSV',
          ['feature', 'size: small', 'good first issue'], """
Ops wants a spreadsheet of the catalog with stock levels, like the existing
orders and customers CSV exports.

### Acceptance criteria
- [ ] `/reports/products.csv` with SKU, name, price, stock, reserved, available, discontinued
- [ ] Linked from the reports page; any logged-in user can download it
- [ ] UTF-8 product names survive the round trip
- [ ] Tests in `tests/test_csvexport.py` and `tests/test_views.py`
""" + GREEN),

    issue('OD-403', '"Reorder" button to copy a past order',
          ['feature', 'size: small'], """
Customers reorder the same items all the time. Clerks want a button on an
order page that creates a new draft for the same customer with the same lines.

### Acceptance criteria
- [ ] Available to admins and clerks on any order except drafts
- [ ] Uses current prices and skips discontinued products, with a flash message listing what was skipped
- [ ] Promo codes are not copied
- [ ] Audit log entry on the new order points to the original
""" + GREEN),

    issue('OD-404', 'Bulk import products from CSV',
          ['feature', 'size: medium'], """
Purchasing sends a supplier price list as CSV every quarter. Admins type the
changes in by hand.

### Acceptance criteria
- [ ] Admin-only upload page that takes a CSV with `sku,name,price,stock`
- [ ] Existing SKUs are updated, new SKUs are created
- [ ] A preview step shows creates/updates/errors before anything is saved
- [ ] One bad row doesn't partially apply the file
- [ ] Every change is audited
- [ ] Tests cover valid files, bad prices, duplicate SKUs and non-UTF-8 input
""" + GREEN),

    issue('OD-405', 'User management screen for admins',
          ['feature', 'size: medium'], """
The only way to add a user or reset a password is `manage.py createuser` on
the server.

### Acceptance criteria
- [ ] Admin-only pages to list, create and deactivate users and change their role
- [ ] Admins can reset a password and regenerate an API token
- [ ] An admin can't deactivate or demote themselves
- [ ] All changes are audited
""" + GREEN),

    issue('OD-406', 'Printable invoice page',
          ['feature', 'size: medium'], """
Accounting copies invoiced orders into a word processor to send them.

### Acceptance criteria
- [ ] `/orders/<number>/invoice` renders a print-friendly invoice (company header, customer, lines, discounts, tax, shipping, total)
- [ ] Only available once the order is invoiced
- [ ] The totals match the order page exactly
- [ ] `GET /api/v1/orders/<number>/invoice` returns the same data as JSON
""" + GREEN),

    issue('OD-407', 'API: customers endpoints and date filters on orders',
          ['feature', 'size: medium'], """
The EDI bridge needs to look up customers and pull orders changed since its
last sync.

### Acceptance criteria
- [ ] `GET /api/v1/customers` (paginated, search by name/account) and `GET /api/v1/customers/<account_number>`
- [ ] `GET /api/v1/orders?updated_since=<ISO-8601>` and `?customer=<account_number>`
- [ ] Bad parameters return `400` with a JSON error
- [ ] README API section updated, tests in `tests/test_api.py`
""" + GREEN),

    issue('OD-408', 'Partial shipments',
          ['feature', 'size: large'], """
The warehouse often ships part of an order when some items are back-ordered.
Right now an order can only be shipped all at once.

### Acceptance criteria
- [ ] Ship a chosen quantity per line; the order shows shipped / remaining per line
- [ ] New status `partially_shipped`; the order moves to `shipped` when everything has shipped
- [ ] Stock is committed per shipment; cancelling releases only what hasn't shipped
- [ ] Each shipment gets a webhook event and an audit entry
- [ ] Available in the UI and the API
- [ ] Existing orders and tests keep working
""" + GREEN),

    issue('OD-409', 'Customer-specific contract pricing',
          ['feature', 'size: large'], """
Big accounts negotiate fixed prices for specific SKUs. Today clerks fake this
with promo codes.

### Acceptance criteria
- [ ] Admins can set a contract price per customer + SKU, optionally with an expiry date
- [ ] When a contract price exists it replaces the list price on new lines; define and document how it interacts with tier, volume and promo discounts
- [ ] The order page shows which lines use contract pricing
- [ ] Pricing tests cover the interaction with every existing discount type
""" + GREEN),

    # ---- tech debt / platform ---------------------------------------------
    issue('OD-301', 'Migrate to Python 3',
          ['tech-debt', 'size: large'], """
Python 2.7 has been end of life since January 2020 and infra won't patch the
2.7 base image any more.

### Acceptance criteria
- [ ] The app and the test suite run on Python 3.12
- [ ] Behavior is unchanged: amounts, rounding, CSV output and the API responses match
- [ ] Existing SQLite databases (including the report cache) keep working or are migrated safely
- [ ] Dockerfile, README and `.python-version` updated
""" + GREEN),

    issue('OD-302', 'Upgrade Flask and its extensions',
          ['tech-debt', 'size: large'], """
Flask 0.10, Flask-Login 0.2, Flask-WTF 0.10, Flask-SQLAlchemy 1.0 and WTForms
2.0 are all years out of date.

### Acceptance criteria
- [ ] Upgrade to the newest versions that still support Python 2.7 (a first step before OD-301)
- [ ] No deprecated `flask.ext.*` imports remain
- [ ] Pins in `requirements.txt` updated
""" + GREEN),

    issue('OD-303', 'Upgrade SQLAlchemy',
          ['tech-debt', 'size: medium'], """
We're on SQLAlchemy 0.9.8.

### Acceptance criteria
- [ ] Upgrade to the newest version compatible with our Python and Flask-SQLAlchemy
- [ ] No new deprecation warnings when running the suite with warnings enabled
""" + GREEN),

    issue('OD-304', 'Replace Flask-Script',
          ['tech-debt', 'size: medium'], """
Flask-Script is unmaintained. Move the `manage.py` commands to the `flask`
CLI (click).

### Acceptance criteria
- [ ] `initdb`, `dropdb`, `seed [--if-empty]`, `createuser`, `shell` and `test` exist as `flask` commands
- [ ] Dockerfile, Makefile and README use the new commands
- [ ] Tests cover the commands with click's test runner
""" + GREEN),

    issue('OD-305', 'Replace nose with pytest',
          ['tech-debt', 'size: medium'], """
nose is unmaintained and doesn't run on modern Python.

### Acceptance criteria
- [ ] The suite runs under pytest with the same number of tests
- [ ] Coverage reporting still works (`make coverage`)
- [ ] Makefile, `setup.cfg`/pytest config and README updated
""" + GREEN),

    issue('OD-306', 'Add database migrations',
          ['tech-debt', 'size: medium'], """
The schema is created with `db.create_all()`. There is no way to change it on
an existing database.

### Acceptance criteria
- [ ] Alembic (or Flask-Migrate) set up with a baseline migration matching the current schema
- [ ] Existing databases can be stamped at the baseline without data loss
- [ ] The Docker entrypoint runs migrations on start
- [ ] README documents how to add a migration
""" + GREEN),

    issue('OD-307', 'Order and account numbers can collide',
          ['bug', 'tech-debt', 'size: medium'], """
Two clerks creating orders at the same time have produced duplicate `SO-`
numbers, which fail with an IntegrityError. The same can happen with customer
account numbers.

### Acceptance criteria
- [ ] Number generation is safe under concurrent requests
- [ ] The existing number formats are kept and existing numbers don't change
- [ ] A test demonstrates two creations in separate sessions get different numbers
""" + GREEN),

    issue('OD-308', 'Webhooks block the request',
          ['tech-debt', 'size: medium'], """
Webhooks are sent inline with a 5 second timeout. When the WMS is down every
order action takes 5+ seconds, and failed events are lost.

### Acceptance criteria
- [ ] Order actions return without waiting for the webhook
- [ ] Failed deliveries are retried with backoff and visible somewhere (table or log)
- [ ] No new infrastructure beyond SQLite (an outbox table plus a worker command is fine)
- [ ] Tests don't make real network calls
""" + GREEN),
]


def gh(args, capture=True):
    result = subprocess.run(['gh'] + args, capture_output=capture, text=True)
    if result.returncode != 0:
        sys.exit('gh %s failed:\n%s' % (' '.join(args[:2]), result.stderr))
    return result.stdout


def existing_keys(repo):
    out = gh(['issue', 'list', '--repo', repo, '--state', 'all',
              '--limit', '1000', '--json', 'title'])
    return {i['title'].split(':', 1)[0] for i in json.loads(out)}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--repo', default='dlapiduz/old-software-inc',
                        help='owner/name (default: %(default)s)')
    parser.add_argument('--dry-run', action='store_true',
                        help='print what would happen, change nothing')
    parser.add_argument('--only', help='comma-separated ticket keys, e.g. OD-201,OD-404')
    args = parser.parse_args()

    issues = ISSUES
    if args.only:
        wanted = set(args.only.split(','))
        issues = [i for i in ISSUES if i['key'] in wanted]
        unknown = wanted - {i['key'] for i in issues}
        if unknown:
            sys.exit('unknown ticket(s): %s' % ', '.join(sorted(unknown)))

    if args.dry_run:
        for i in issues:
            print('%-60s [%s]' % (i['title'][:60], ', '.join(i['labels'])))
        print('\n%d issues, %d labels (dry run, nothing created)' % (len(issues), len(LABELS)))
        return

    for name, (color, description) in LABELS.items():
        gh(['label', 'create', name, '--repo', args.repo, '--color', color,
            '--description', description, '--force'])

    have = existing_keys(args.repo)
    created = skipped = 0
    for i in issues:
        if i['key'] in have:
            print('skip    %s (already exists)' % i['key'])
            skipped += 1
            continue
        cmd = ['issue', 'create', '--repo', args.repo, '--title', i['title'],
               '--body', i['body']]
        for label in i['labels']:
            cmd += ['--label', label]
        url = gh(cmd).strip()
        print('created %s %s' % (i['key'], url))
        created += 1
    print('\n%d created, %d skipped' % (created, skipped))


if __name__ == '__main__':
    main()
