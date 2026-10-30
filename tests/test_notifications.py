import socket
import urllib2

import mock
import simplejson as json
from nose.tools import eq_

from orderdesk.notifications import notify

from base import AppTestCase

URL = 'http://wms.oldsoftware.example/hooks/orderdesk'


class NotifyTest(AppTestCase):

    def test_disabled_without_url(self):
        with mock.patch('orderdesk.notifications.urllib2.urlopen') as urlopen:
            eq_(notify('order.submitted', {}), False)
            self.assertFalse(urlopen.called)

    @mock.patch('orderdesk.notifications.urllib2.urlopen')
    def test_posts_json(self, urlopen):
        self.app.config['WEBHOOK_URL'] = URL
        eq_(notify('order.submitted', {'number': 'SO-000001', 'total_cents': 1500L}), True)

        req = urlopen.call_args[0][0]
        eq_(req.get_full_url(), URL)
        eq_(req.get_method(), 'POST')
        eq_(req.get_header('Content-type'), 'application/json')
        eq_(urlopen.call_args[1]['timeout'], 5)

        body = json.loads(req.get_data())
        eq_(body['event'], 'order.submitted')
        eq_(body['payload'], {'number': 'SO-000001', 'total_cents': 1500})
        self.assertTrue('sent_at' in body)

    @mock.patch('orderdesk.notifications.urllib2.urlopen')
    def test_failures_are_swallowed(self, urlopen):
        self.app.config['WEBHOOK_URL'] = URL
        urlopen.side_effect = urllib2.URLError('connection refused')
        eq_(notify('order.shipped', {}), False)

        urlopen.side_effect = socket.timeout('timed out')
        eq_(notify('order.shipped', {}), False)
