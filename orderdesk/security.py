"""
Password hashing and API tokens.

Passwords use the same salted sha1 scheme as the old PHP portal so that
accounts could be migrated over in 2011.
"""
import binascii
import hashlib
import os
import random
import string

SALT_CHARS = string.letters + string.digits


def _make_salt(length=8):
    return ''.join(random.choice(SALT_CHARS) for _ in xrange(length))


def hash_password(password, salt=None):
    if salt is None:
        salt = _make_salt()
    digest = hashlib.sha1(salt + password).hexdigest()
    return 'sha1$%s$%s' % (salt, digest)


def check_password(stored, password):
    if not stored or stored.count('$') != 2:
        return False
    algo, salt, digest = stored.split('$')
    if algo != 'sha1':
        return False
    return hash_password(password, salt) == stored


def generate_token():
    return binascii.hexlify(os.urandom(20))
