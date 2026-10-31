# OrderDesk

> [!WARNING]
> **For testing only. Do not use this in production.**
>
> OrderDesk is a deliberately outdated sample application. It exists to test
> automated software tooling ("software factories", coding agents, migration
> tools) on bug fixes, library changes and updates, and large refactors.
> "Old Software Inc." is a fictional company.
>
> * **End-of-life language.** The app runs only on Python 2.7, which reached
>   end of life on January 1, 2020 and no longer gets security fixes. The
>   `python:2.7.18` Docker base image is unmaintained too.
> * **Old, unpatched libraries.** Every dependency is pinned to a version from
>   around 2014 (Flask 0.10, Werkzeug 0.9, Jinja2 2.7, SQLAlchemy 0.9 and
>   others). Many of these versions have publicly known vulnerabilities. For
>   example, the Werkzeug debugger in this version has no PIN protection, so
>   running in development mode on a reachable interface allows remote code
>   execution.
> * **Intentional bugs and insecure practices.** The code includes planted
>   bugs and weak security on purpose: salted SHA-1 password hashing, an
>   open redirect, forms without CSRF protection, a default secret key and
>   pickled data in the database. See `BACKLOG.md`. Please don't report these
>   as security issues; they are part of the test fixture.
>
> Run it only locally or in a disposable container. Don't expose it to the
> internet, and don't store real customer data, credentials or anything else
> sensitive in it.

Internal order management for **Old Software Inc.**, an industrial supply
distributor. Clerks enter B2B orders for customer accounts, admins approve
them, the warehouse ships them and accounting invoices them. The warehouse
system (WMS) and the EDI bridge use the JSON API.

* Customers with pricing tiers (standard / silver / gold / platinum), tax
  exemption and credit limits
* Product catalog with stock on hand and reserved stock
* Order workflow: `draft -> submitted -> approved -> shipped -> invoiced`
  (or `cancelled`), with stock reservation, credit checks and an audit trail
* Pricing: volume discounts, tier discounts, promo codes, sales tax, shipping
* Sales reports, CSV exports
* JSON API (`/api/v1`) with per-user API tokens
* Outbound webhooks on order events

## Stack

Python **2.7** only. All versions are pinned in `requirements.txt` and
`requirements-dev.txt`.

| What          | Library                                    |
|---------------|--------------------------------------------|
| Web           | Flask 0.10.1, Werkzeug 0.9.6, Jinja2 2.7.3 |
| ORM           | SQLAlchemy 0.9.8, Flask-SQLAlchemy 1.0     |
| Auth          | Flask-Login 0.2.11                         |
| Forms         | Flask-WTF 0.10.3, WTForms 2.0.1            |
| CLI           | Flask-Script 2.0.5                         |
| Misc          | simplejson, unicodecsv, python-dateutil    |
| Tests         | nose 1.3.4, mock 1.0.1, coverage 3.7.1     |
| Database      | SQLite                                     |

## Running it

### Docker (easiest)

```sh
make docker-run          # http://localhost:5050 (macOS AirPlay owns :5000)
make docker-test         # run the test suite in the container
```

### Local Python 2.7

You need a Python 2.7 interpreter (`.python-version` pins 2.7.18). Use
`pyenv install 2.7.18` or `mise install python@2.7.18`. Both compile it from
source and build their own OpenSSL 1.1.

```sh
python2.7 -m pip install 'virtualenv<20.22'
make install             # creates ./venv
make test
make run                 # seeds demo data on first run, serves on :5000
```

Or do it by hand:

```sh
python manage.py seed               # create tables + demo data
python manage.py runserver          # dev server, debugger on
python manage.py shell
python manage.py createuser
python manage.py -c production initdb
```

### Demo logins

| User   | Password  | Role                                   |
|--------|-----------|----------------------------------------|
| admin  | admin123  | everything, incl. approvals & products |
| clerk  | clerk123  | customers and orders                   |
| viewer | viewer123 | read only                              |

`manage.py seed` prints each user's API token.

## Configuration

See `config.py`. Environment variables:

* `ORDERDESK_ENV`: `development` (default), `testing` or `production`
* `ORDERDESK_DB`: SQLAlchemy URL, default `sqlite:///orderdesk.db`
* `ORDERDESK_SECRET`: Flask secret key
* `ORDERDESK_WEBHOOK`: URL that order events are POSTed to

## API

Send `X-OrderDesk-Token: <token>` (or `?token=`).

```
GET  /api/v1/products[?include_discontinued=1]
GET  /api/v1/products/<sku>
GET  /api/v1/orders[?status=submitted&limit=50]
GET  /api/v1/orders/<number>
POST /api/v1/orders                      {"customer": "C-00001",
                                          "lines": [{"sku": "WID-1001", "quantity": 10}],
                                          "promo_code": "SPRING14", "submit": true}
POST /api/v1/orders/<number>/<action>    action = submit|approve|ship|invoice|cancel
```

## Layout

```
config.py              configuration classes
manage.py              Flask-Script commands
orderdesk/
  __init__.py          app factory
  models.py            SQLAlchemy models
  money.py             Money type (integer cents)
  pricing.py           discounts, tax, shipping
  inventory.py         stock reservation
  workflow.py          order state machine
  reports.py           sales reports + pickle cache
  csvexport.py         CSV exports
  notifications.py     webhooks (urllib2)
  security.py          password hashing, API tokens
  seed.py              demo data
  views/               blueprints (html + api)
  templates/ static/
tests/                 nose test suite
BACKLOG.md             open tickets
scripts/create_issues.py  creates the backlog as GitHub issues (Python 3 + gh)
```

To (re)create the GitHub issues and labels, run `scripts/create_issues.py --dry-run`
first, then without `--dry-run`. It skips tickets that already exist.

## Tests

```sh
nosetests tests                                    # or: make test
nosetests tests --with-coverage --cover-package=orderdesk
python manage.py test
```

Tests use an in-memory SQLite database and the `testing` config.

CI (GitHub Actions) runs the suite in Docker with a coverage floor, plus the
repository policies in [CONTRIBUTING.md](CONTRIBUTING.md) (`make policies`).

## License

MIT, see [LICENSE](LICENSE). The software is provided "as is", without
warranty of any kind. See the warning at the top of this file before running it.
