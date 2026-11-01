Implement `plan.md` for issue #{{ inputs.issue_number }}: {{ inputs.issue_title }}.

Rules from `CONTRIBUTING.md` that CI enforces on the pull request:
- Change tests with the code: anything under `orderdesk/`, `manage.py` or
  `config.py` needs a matching change under `tests/`.
- Don't reduce the number of `test_*` functions, and keep total coverage of
  `orderdesk/` at or above 90%.
- Pin any new requirement with `==`. No debugger leftovers, no secrets, no
  `*.pyc`/`*.db`/`.coverage` files.
- Keep behavior outside the ticket unchanged; the existing tests are the contract.
- This is Python 2.7 on purpose. Don't modernize code you aren't changing.

Run `nosetests tests` yourself before you finish. Delete `plan.md` when you are
done; it must not end up in the pull request.

Your final message becomes part of the pull request description. Start it with
a one-line summary and include `Fixes #{{ inputs.issue_number }}` on its own line.
