#!/usr/bin/env python3
"""
Repository policies, checked in CI (see CONTRIBUTING.md).

Like create_issues.py this is repo tooling: host Python 3, stdlib only.

    scripts/check_policies.py                       # repo-wide checks
    scripts/check_policies.py --base origin/main    # plus pull request checks

Pull request checks read PR_TITLE and PR_LABELS (a JSON list of label names)
from the environment when they are set.
"""
import argparse
import json
import os
import re
import subprocess
import sys

TICKET_TITLE = re.compile(r'^OD-\d+\b')
PINNED = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*(\[[A-Za-z0-9,._-]+\])?==[A-Za-z0-9.+!-]+$')
TEST_DEF = re.compile(r'^\s*def (test\w*)\(', re.M)
SECRETS = [
    ('private key', re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----')),
    ('AWS access key', re.compile(r'\bAKIA[0-9A-Z]{16}\b')),
    ('GitHub token', re.compile(r'\b(gh[pousr]_[A-Za-z0-9]{36,}|github_pat_[A-Za-z0-9_]{60,})\b')),
    ('Slack token', re.compile(r'\bxox[abposr]-[A-Za-z0-9-]{10,}\b')),
]
DEBUG_LEFTOVERS = re.compile(r'\b(pdb\.set_trace\(|import i?pdb\b|breakpoint\(\))')
FORBIDDEN_PATHS = re.compile(r'(^_factory/|\.db$|\.pyc$|^\.coverage$)')
SOURCE = re.compile(r'^(orderdesk/.*\.py|manage\.py|config\.py)$')

# Labels a maintainer can put on a PR to waive one check.
WAIVE_TESTS = 'no-tests-needed'
WAIVE_TEST_REMOVAL = 'tests-removed-ok'


def git(*args):
    return subprocess.run(('git',) + args, capture_output=True, text=True,
                          check=True).stdout


def tracked_files():
    return git('ls-files').splitlines()


def read(path):
    with open(path, encoding='utf-8', errors='replace') as f:
        return f.read()


# ---- repo-wide ------------------------------------------------------------

def check_pinned_requirements(files):
    """Every dependency is pinned to an exact version."""
    problems = []
    for path in files:
        if not re.match(r'^requirements[^/]*\.txt$', path):
            continue
        for n, line in enumerate(read(path).splitlines(), 1):
            line = line.split('#', 1)[0].strip()
            if line and not line.startswith('-') and not PINNED.match(line):
                problems.append('%s:%d: %r is not pinned with ==' % (path, n, line))
    return problems


def check_forbidden_files(files):
    """No grader notes, databases or build artifacts in git."""
    return ['%s must not be committed' % p for p in files if FORBIDDEN_PATHS.search(p)]


def check_required_notices(files):
    """The testing-only warning and the license stay in place."""
    problems = []
    if 'LICENSE' not in files:
        problems.append('LICENSE is missing')
    if 'README.md' not in files or 'For testing only' not in read('README.md'):
        problems.append('README.md must keep the "For testing only" warning')
    return problems


def check_no_secrets(files):
    """No credentials in tracked files."""
    problems = []
    for path in files:
        if not os.path.isfile(path):
            continue
        text = read(path)
        for name, pattern in SECRETS:
            for m in pattern.finditer(text):
                line = text.count('\n', 0, m.start()) + 1
                problems.append('%s:%d: looks like a %s' % (path, line, name))
    return problems


def check_no_debug_leftovers(files):
    """No debugger calls left in app or test code."""
    problems = []
    for path in files:
        if path.endswith('.py') and os.path.isfile(path) and path != 'scripts/check_policies.py':
            for n, line in enumerate(read(path).splitlines(), 1):
                if DEBUG_LEFTOVERS.search(line):
                    problems.append('%s:%d: %s' % (path, n, line.strip()))
    return problems


# ---- pull requests --------------------------------------------------------

def count_tests(rev=None):
    names = (git('ls-tree', '-r', '--name-only', rev, 'tests/').splitlines()
             if rev else git('ls-files', 'tests/').splitlines())
    total = 0
    for path in names:
        if path.endswith('.py'):
            text = git('show', '%s:%s' % (rev, path)) if rev else read(path)
            total += len(TEST_DEF.findall(text))
    return total


def check_pr_title(title, labels):
    """PR titles start with the ticket they address, e.g. "OD-201: ..."."""
    if title is None:
        return []
    if not TICKET_TITLE.match(title.strip()):
        return ['PR title %r must start with a ticket key such as "OD-201: "' % title]
    return []


def check_tests_with_code(changed, labels):
    """A change to app code comes with a change to the tests."""
    if WAIVE_TESTS in labels:
        return []
    source = [p for p in changed if SOURCE.match(p)]
    tests = [p for p in changed if p.startswith('tests/')]
    if source and not tests:
        return ['app code changed (%s) but nothing under tests/ did; add a test '
                'or ask a maintainer for the %r label' % (', '.join(source[:5]), WAIVE_TESTS)]
    return []


def check_test_count(base, labels):
    """The number of test functions never goes down."""
    if WAIVE_TEST_REMOVAL in labels:
        return []
    before, after = count_tests(base), count_tests()
    if after < before:
        return ['test functions went from %d to %d; removing tests needs the %r label'
                % (before, after, WAIVE_TEST_REMOVAL)]
    return []


def main():
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--base', help='base revision for pull request checks')
    args = parser.parse_args()

    os.chdir(git('rev-parse', '--show-toplevel').strip())
    files = tracked_files()
    checks = [
        ('pinned requirements', check_pinned_requirements(files)),
        ('forbidden files', check_forbidden_files(files)),
        ('required notices', check_required_notices(files)),
        ('no secrets', check_no_secrets(files)),
        ('no debugger leftovers', check_no_debug_leftovers(files)),
    ]
    if args.base:
        labels = set(json.loads(os.environ.get('PR_LABELS') or '[]'))
        merge_base = git('merge-base', args.base, 'HEAD').strip()
        changed = git('diff', '--name-only', merge_base, 'HEAD').splitlines()
        checks += [
            ('PR title names a ticket', check_pr_title(os.environ.get('PR_TITLE'), labels)),
            ('tests change with code', check_tests_with_code(changed, labels)),
            ('test count does not drop', check_test_count(merge_base, labels)),
        ]

    failed = 0
    for name, problems in checks:
        print('%s %s' % ('FAIL' if problems else 'ok  ', name))
        for p in problems:
            print('       ' + p)
        failed += bool(problems)
    if failed:
        sys.exit('\n%d of %d policies failed' % (failed, len(checks)))
    print('\nall %d policies passed' % len(checks))


if __name__ == '__main__':
    main()
