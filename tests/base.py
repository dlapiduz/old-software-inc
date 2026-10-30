import unittest

import simplejson as json

from orderdesk import create_app
from orderdesk.extensions import db


class AppTestCase(unittest.TestCase):

    def setUp(self):
        self.app = create_app('testing')
        self.ctx = self.app.test_request_context()
        self.ctx.push()
        db.create_all()
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()

    def login(self, user, password='secret'):
        db.session.commit()
        return self.client.post('/login', data={'username': user.username,
                                                'password': password},
                                follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def api(self, method, path, user=None, data=None):
        headers = {}
        if user is not None:
            headers['X-OrderDesk-Token'] = user.api_token
        kwargs = {'headers': headers}
        if data is not None:
            kwargs['data'] = json.dumps(data)
            kwargs['content_type'] = 'application/json'
        db.session.commit()
        resp = getattr(self.client, method)('/api/v1' + path, **kwargs)
        resp.json_body = json.loads(resp.data) if resp.data else None
        return resp
