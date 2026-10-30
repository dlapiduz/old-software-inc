import unittest

from nose.tools import eq_

from orderdesk.security import check_password, generate_token, hash_password


class PasswordTest(unittest.TestCase):

    def test_hash_format(self):
        hashed = hash_password('hunter2', salt='abcdefgh')
        algo, salt, digest = hashed.split('$')
        eq_(algo, 'sha1')
        eq_(salt, 'abcdefgh')
        eq_(len(digest), 40)

    def test_known_hash(self):
        # value produced by the old PHP portal for password "secret", salt "OSIsalt1"
        eq_(hash_password('secret', 'OSIsalt1'),
            'sha1$OSIsalt1$0333eea88718835254af53c1fe3d7e59b078e85e')

    def test_random_salt(self):
        self.assertNotEqual(hash_password('secret'), hash_password('secret'))

    def test_check_password(self):
        hashed = hash_password('secret')
        self.assertTrue(check_password(hashed, 'secret'))
        self.assertTrue(check_password(hashed, u'secret'))
        self.assertFalse(check_password(hashed, 'Secret'))

    def test_check_password_rejects_bad_hashes(self):
        self.assertFalse(check_password(None, 'secret'))
        self.assertFalse(check_password('', 'secret'))
        self.assertFalse(check_password('plaintext', 'secret'))
        self.assertFalse(check_password('md5$abc$def', 'secret'))

    def test_generate_token(self):
        token = generate_token()
        eq_(len(token), 40)
        self.assertNotEqual(token, generate_token())
