"""
Outbound webhooks. The warehouse system (WMS) listens for order events.
"""
import logging
import socket
import urllib2
from datetime import datetime

import simplejson as json
from flask import current_app

log = logging.getLogger(__name__)


def notify(event, payload):
    url = current_app.config.get('WEBHOOK_URL')
    if not url:
        return False
    body = json.dumps({
        'event': event,
        'payload': payload,
        'sent_at': datetime.utcnow().isoformat(),
    })
    req = urllib2.Request(url, body, {
        'Content-Type': 'application/json',
        'User-Agent': 'OrderDesk/1.4',
    })
    try:
        resp = urllib2.urlopen(req, timeout=current_app.config.get('WEBHOOK_TIMEOUT', 5))
        resp.read()
        return True
    except (urllib2.URLError, socket.timeout), e:
        log.warning('webhook %s to %s failed: %s', event, url, e)
        return False
