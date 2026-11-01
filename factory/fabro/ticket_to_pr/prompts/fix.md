The test gate failed for issue #{{ inputs.issue_number }}. The gate runs:

    nosetests tests --with-coverage --cover-package=orderdesk --cover-erase
    coverage report --include='orderdesk/*' --fail-under=90

Read the failure output from the previous stage, find the cause, and fix it.
Fix the code, not the tests, unless a test you wrote for this ticket is itself
wrong. Never delete or weaken an existing test to get green, and don't lower
`COVERAGE_FLOOR`. If coverage is the problem, add tests for the code you added.

Run the two commands above yourself before you finish.
