# Plan: OD-410 — add `GET /health` (issue #36)

Fixes #36. PR title: `OD-410: Add a /health endpoint`.

## Behavior

- `GET /health` returns HTTP 200, body `{"status": "ok"}`, and
  `Content-Type: application/json`.
- No login. The route has no `@login_required`, so an anonymous request gets
  200, not a 302 to `/login`.
- No database access. The handler does not query, add or commit anything, and
  writes no audit entry. It is a shallow liveness check: it returns 200
  whatever the state of the database. The issue asks for "is OrderDesk up",
  and "does not touch the database" is an explicit criterion, so a DB ping is
  out of scope.
- The route lives on the existing `main` blueprint, which is registered without
  a URL prefix, so the path is `/health`. It does not collide with `/` or
  `/api/v1/...`.

## Files to change

1. `orderdesk/views/main.py`
   - Change the import to `from flask import Blueprint, jsonify, render_template`.
   - Add a view, with no decorator:

     ```python
     @bp.route('/health')
     def health():
         return jsonify(status='ok')
     ```

   - Flask's `jsonify` sets `application/json` and does not touch `db` or the
     session.

2. `tests/test_views.py`
   - Add `import simplejson as json` (same import as `tests/base.py`) and
     `from sqlalchemy import event`.
   - Add a `HealthViewsTest(AppTestCase)` class after `DashboardTest`, with three
     tests:
     - `test_health_returns_ok_json`: `GET /health` returns 200;
       `resp.mimetype == 'application/json'`; `json.loads(resp.data) == {'status': 'ok'}`.
       Parse the body rather than comparing raw bytes. Flask 0.10 may emit it
       compact or pretty-printed, depending on settings.
     - `test_health_needs_no_login`: no `self.login(...)`. Assert 200 and that
       there is no `Location` header, so there is no redirect to login.
     - `test_health_does_not_touch_database`: attach a
       `before_cursor_execute` listener to `db.engine` that records statements,
       make the request, remove the listener in a `try/finally`, then assert
       both that the response is 200 and that no statements were recorded. The
       200 assertion matters: without the route, the request would 404 and the
       empty-statement check alone would pass vacuously.

   No change to `tests/base.py` is needed. `AppTestCase` already gives an
   in-memory SQLite engine and a pushed app context, which `db.engine` requires.

No other files change. Not in scope: README/API docs, version bump in
`orderdesk/__init__.py`, deep health checks, and auth on the endpoint.

## Tests that prove it

Each new test fails before the change, because `/health` returns 404 without
the route. This is a feature, not a bug fix, so the regression requirement is
met by the same tests.

- `test_health_returns_ok_json` covers the status code, body and content type.
- `test_health_needs_no_login` covers anonymous access.
- `test_health_does_not_touch_database` covers the no-DB criterion.

Existing tests are unaffected: no other route or shared fixture changes.

## Verification

- `make docker-test`: the acceptance-criteria check, full nose suite in the
  container. Must be green.
- `make docker-coverage`: the coverage floor is 90% of `orderdesk/`. The new
  view is fully covered by the new tests.
- `make policies` (needs Python 3, which this sandbox lacks): the "Tests change
  with code" check is satisfied by the `tests/test_views.py` change. The test
  count goes up by 3. The PR title must start with `OD-410:`, and the PR body
  must include `Fixes #36`.

## Risks

- Flask 0.10.1 / Werkzeug 0.9.6 pinning: `jsonify` should return
  `application/json` with no charset. The test checks `resp.mimetype`, which
  ignores parameters, so a charset suffix would not break it. If the exact
  header matters, the test should compare `resp.headers['Content-Type']`
  instead.
- The DB check relies on SQLAlchemy 0.9.8 `event.listen` / `event.remove` on an
  engine. Both exist in that version.
