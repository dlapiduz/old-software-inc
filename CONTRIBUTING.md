# Contributing

Read the warning at the top of `README.md` first: this repo is a test
fixture, and its old code and libraries are intentional.

Work is tracked as GitHub issues with keys like `OD-201`. Each issue's
acceptance criteria say what "done" means.

## Policies

CI enforces these on every push to `main` and every pull request. Run them
locally with `make policies` (needs Python 3 and git) and `make docker-coverage`.

| Policy | What it checks | Waiver label |
|---|---|---|
| Tests pass | the full suite passes in the Docker image (`.github/workflows/ci.yml`) | – |
| Coverage floor | total coverage of `orderdesk/` stays at or above `COVERAGE_FLOOR` in the `Makefile` (90%; it is 91% now, counting modules the tests never import) | – |
| Pinned requirements | every line in `requirements*.txt` pins an exact version with `==` | – |
| Forbidden files | no `_factory/`, `*.db`, `*.pyc` or `.coverage` files in git | – |
| Required notices | `LICENSE` exists and `README.md` keeps the "For testing only" warning | – |
| No secrets | tracked files contain no private keys or AWS, GitHub or Slack tokens | – |
| No debugger leftovers | no `pdb.set_trace()`, `import pdb`/`ipdb` or `breakpoint()` | – |
| PR title names a ticket | the PR title starts with an issue key, e.g. `OD-201: Tax after discounts` | – |
| Tests change with code | a PR that changes `orderdesk/`, `manage.py` or `config.py` also changes something under `tests/` | `no-tests-needed` |
| Test count does not drop | a PR doesn't reduce the number of `test_*` functions | `tests-removed-ok` |

Waiver labels are for maintainers. Don't add them to your own PR to get it
past CI. If a policy is wrong for a ticket (for example, OD-305 moves the
suite to pytest), say so in the PR description.

The policy checks live in `scripts/check_policies.py`. They're Python 3 repo
tooling, separate from the Python 2.7 app.

## Pull requests

- One ticket per PR. Put the key in the title and `Fixes #<issue number>` in the description.
- Bug fixes come with a regression test that fails without the fix.
- Keep behavior that isn't part of the ticket unchanged. The tests are the contract.
