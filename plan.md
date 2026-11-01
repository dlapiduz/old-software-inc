# Plan: OD-411 — Add a version endpoint (issue #38)

Fixes #38

## Context

- The app version already exists as `__version__ = '1.4.2'` in
  `orderdesk/__init__.py:15`. It is shown only in the footer of HTML pages
  (`orderdesk/templates/base.html:35`, injected by the context processor at
  `orderdesk/__init__.py:67-73`). No endpoint exposes it, so customers
  calling the JSON API cannot see it.
- The JSON API lives in `orderdesk/views/api.py`, mounted at `/api/v1`
  (`orderdesk/__init__.py:50`). Every existing route there is decorated with
  `@token_required`, and the README's API section lists them.
- Tests for the API are in `tests/test_api.py`. They use the `self.api(method,
  path, user)` helper from `tests/base.py`, which prefixes `/api/v1` and
  parses `json_body`.

## Decisions (defaults chosen; no maintainer question needed)

- **Path:** `GET /api/v1/version`. It sits beside the other API routes and
  does not clash with `/orders/<number>/<action>`.
- **Auth:** require an API token like every other `/api/v1` route. This keeps
  build information out of anonymous requests. The README says the app is not
  for internet exposure, but the consistent choice is still token-gated. If
  the maintainer wants it public, drop `@token_required` on this one route and
  add a test for that instead.
- **Content:** the value of `orderdesk.__version__`, which is the only build
  identifier the app has. No git SHA is added, because the Docker image does
  not ship git metadata and the issue asks only for "the version".
- **Response:** `200` with JSON `{"version": "1.4.2"}`, following the shape of
  the other endpoints (`{"products": ...}`, `{"order": ...}`).

## Files to change

1. `orderdesk/views/api.py`
   - Add a route after `list_products` or at the end of the file:
     ```python
     @bp.route('/version')
     @token_required
     def version():
         return jsonify(version=__version__)
     ```
   - Import `__version__` with `from orderdesk import __version__`. Check that
     this does not create a circular import. `orderdesk/__init__.py` imports
     `views` only inside `_register_blueprints`, which runs after
     `__version__` is defined, so the import should be safe. Confirm by
     running the suite.

2. `tests/test_api.py`
   - Add the tests listed below.

3. `README.md`
   - Add `GET /api/v1/version` to the API block (lines 116-124) so the
     endpoint is documented.

No other files change. In particular, do not touch `__version__`, the footer,
the config, or the policy scripts.

## Behavior to add

- `GET /api/v1/version` with a valid token returns `200` and
  `{"version": <__version__>}`.
- Without a token, or with an invalid or inactive user's token, it returns
  `401` with the usual `{"error": "invalid or missing API token"}` body.
- The token may be passed in the header or as `?token=`, as with other
  routes.

## Tests (in `tests/test_api.py`)

1. `test_version` — with `self.clerk`, `GET /version` returns `200`, and
   `json_body == {'version': orderdesk.__version__}` (import `__version__` from
   `orderdesk`). This test fails before the change because the route returns
   `404`.
2. `test_version_requires_token` — `self.api('get', '/version')` with no user
   returns `401`, and an inactive user's token (`make_user(active=False)`)
   also returns `401`. This guards the auth decision.

These are new features, not bug fixes, so no regression-first requirement
applies. The test count goes up, so the "test count does not drop" policy
passes. The "tests change with code" policy passes because `tests/` changes
alongside `orderdesk/`.

## Verification

- `make docker-test` (the acceptance criterion) passes, including both new
  tests.
- `make docker-coverage` keeps coverage at or above the 90% floor. The new
  route is covered by test 1.
- `make policies` passes locally (`python3 scripts/check_policies.py`). Before
  opening the PR, run it with `--base origin/main` so the PR-title and
  test-count checks are included. The PR title must start with `OD-411:`.
- Optional manual check: `make docker-run`, log in, create a token via
  `manage.py seed` output, and run
  `curl -H "X-OrderDesk-Token: <token>" http://localhost:5050/api/v1/version`.
  Expect `{"version": "1.4.2"}`.

## Out of scope

- Adding a git SHA, build date, or Docker tag to the response.
- Making the endpoint anonymous. This is only a change if the maintainer asks
  for it, as noted above.
- Changing the footer or `__version__`.
