# Plan: OD-410 — Add a `/health` endpoint (issue #36)

## Context

- `orderdesk/__init__.py` `create_app()` registers the blueprints and has no
  `before_request` hook, so a new route is not gated by anything global.
- `orderdesk/views/main.py` is the blueprint with no URL prefix (it serves `/`).
  `/health` belongs there, next to the dashboard. It is not under `/api/v1`, so
  the API token check does not apply.
- Access control is per view via `flask.ext.login.login_required`. The health
  route will simply omit it.
- Flask-Login 0.2.11 only loads the user (a DB query through `load_user`) when
  `current_user` is accessed. The new view will not touch `current_user`,
  `session`, or the models, so it will not query the database.
- JSON responses in the app use `flask.jsonify` (see `orderdesk/views/api.py`),
  which sets `Content-Type: application/json`.

## Files to change

1. **`orderdesk/views/main.py`**
   - Import `jsonify` from `flask` (alongside `Blueprint`, `render_template`).
   - Add a view with no decorators other than the route:

     ```python
     @bp.route('/health')
     def health():
         return jsonify(status='ok')
     ```

   - Do not add `login_required`, do not read `current_user`, and do not query
     any model.

2. **`tests/test_views.py`**
   - Add `import simplejson as json` (the same library `tests/base.py` uses) to
     parse the response body.
   - Add a new test class `HealthViewsTest(AppTestCase)` with these tests. No
     login is performed in any of them, which covers the anonymous-access
     criterion:
     - `test_health_returns_ok`: `GET /health` returns status 200, and
       `json.loads(resp.data) == {'status': 'ok'}`.
     - `test_health_is_json`: `resp.mimetype == 'application/json'`.
     - `test_health_does_not_redirect`: status is 200 and the `Location` header
       is absent, so an anonymous request is not sent to `/login`.
     - `test_health_does_not_touch_database`: attach a listener with
       `sqlalchemy.event.listen(db.engine, 'before_cursor_execute', ...)` that
       records statements, call `GET /health`, then remove the listener with
       `event.remove`. Assert that no statements were recorded. Remove the
       listener in a `try/finally` so it cannot leak into other tests.

   Without the new route, every one of these tests fails (the request returns
   404), so the tests prove the endpoint exists and behaves as specified. This
   is a new feature rather than a bug fix, so no separate regression test is
   needed.

No other files change. `README.md` is not updated, because the issue does not
ask for documentation and the README's API section covers `/api/v1` only.

## Behavior

| Request | Response |
|---|---|
| `GET /health` (anonymous or logged in) | `200 OK`, body `{"status": "ok"}`, `Content-Type: application/json` |
| `GET /health` | No `Location` header, no redirect to `/login`, no database query |

## Verification

1. Targeted: `nosetests tests/test_views.py:HealthViewsTest -v`, which should
   show the four new tests passing. Optionally confirm they fail with the
   route removed.
2. Full suite: `make docker-test` (`docker run --rm orderdesk nosetests tests`).
   This is the issue's acceptance criterion. If Docker is unavailable, use
   `make install && make test` with Python 2.7.
3. Coverage floor: `make docker-coverage`, which checks `orderdesk/` against
   `COVERAGE_FLOOR` (90%). The new route is fully covered by the new tests.
4. Repository policies: `make policies`. Relevant checks:
   - "Tests change with code": `orderdesk/` and `tests/` both change.
   - "Test count does not drop": four `test_*` functions are added.
   - "PR title names a ticket": the title is `OD-410: Add a /health endpoint`.
   - Pinned requirements, forbidden files, and secrets are unaffected.

## Pull request

- Title: `OD-410: Add a /health endpoint`
- Description includes `Fixes #36`.
- No waiver labels.

## Out of scope

- Checking the database or other dependencies inside `/health`. The issue asks
  for a cheap liveness check that does not touch the database.
- Changing the Flask-Login or `load_user` behavior.
- Adding `/health` under `/api/v1` or requiring an API token.
