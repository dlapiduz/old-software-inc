# -*- coding: utf-8 -*-
import re
import unicodedata

from dateutil import parser as date_parser
from flask import current_app

_slug_strip = re.compile(r'[^\w\s-]')
_slug_hyphenate = re.compile(r'[-\s]+')


class Page(object):

    def __init__(self, query, page, per_page):
        if page < 1:
            page = 1
        self.page = page
        self.per_page = per_page
        self.total = query.count()
        self.items = query.limit(per_page).offset((page - 1) * per_page).all()
        self.pages = self.total / per_page or 1

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1

    @property
    def next_num(self):
        return self.page + 1


def paginate(query, page=1, per_page=None):
    if per_page is None:
        per_page = current_app.config['ITEMS_PER_PAGE']
    return Page(query, page or 1, per_page)


def slugify(value):
    if not isinstance(value, unicode):
        value = value.decode('utf-8')
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = _slug_strip.sub('', value).strip().lower()
    return _slug_hyphenate.sub('-', value)


def parse_date(value):
    if not value:
        return None
    try:
        return date_parser.parse(value).date()
    except (ValueError, TypeError), e:
        return None
