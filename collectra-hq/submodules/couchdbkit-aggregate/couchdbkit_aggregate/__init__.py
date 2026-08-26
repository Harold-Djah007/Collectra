from __future__ import absolute_import
from __future__ import unicode_literals
from . import fn
#from memoize import memoize

__all__ = ['AggregateView', 'KeyView', 'AggregateKeyView']


class KeyView(object):
    def __init__(self, key, reduce_fn=None, startkey_fn=None, endkey_fn=None,
                 couch_view=None, db=None):
        """
        key -- the individual key/field/slug in the CouchDB map output
        reduce_fn -- reduce function for values of key (default: sum)
        startkey_fn -- see CouchView
        endkey_fn -- see CouchView
        db -- the couchdbkit Database object
        couch_view -- the view name

        If reduce_fn is an instance (or subclass) of CouchReduceFunction,
        get_value() will do a reduce query under the hood, otherwise it will do
        a map query and return reduce_fn(values).

        If db or couch_view are not specified, you must specify them when
        calling get_value().

        """
        if isinstance(reduce_fn, type):
            reduce_fn = reduce_fn()

        self.key_slug = [key] if key else []
        self.reduce_fn = reduce_fn or fn.sum()
        self.is_couch_reduce = isinstance(self.reduce_fn, fn.CouchReduceFunction)

        self.startkey_fn = startkey_fn or (lambda x: x)
        self.endkey_fn = endkey_fn or (lambda x: x + [{}])

        self.couch_view = couch_view
        self.db = db

    #@memoize
    def get_value(self, key, startkey=None, endkey=None, couch_view=None,
                  db=None, **kwargs):
        startkey = key + self.key_slug + self.startkey_fn(startkey or [])
        endkey = key + self.key_slug + self.endkey_fn(endkey or [])

        result = (self.db or db).view(
            self.couch_view or couch_view,
            reduce=self.is_couch_reduce,
            startkey=startkey,
            endkey=endkey,
            wrapper=lambda r: r['value'],
            **kwargs)

        if self.is_couch_reduce:
            result = result.first()

        return self.reduce_fn(result)


class AggregateKeyView(object):
    def __init__(self, fn=None, *key_views):
        """
        key_views -- the KeyViews whose results to pass to the calculation
        fn -- the function to apply to the key_views

        """
        self.key_views = key_views
        self.fn = fn

    def get_value(self, key, **kwargs):
        return self.fn(*[v.get_value(key, **kwargs) for v in self.key_views]) 


class ViewCollector(type):
    def __new__(cls, name, bases, attrs):
        key_views = {}

        for name, attr in attrs.items():
            if isinstance(attr, (KeyView, AggregateKeyView)):
                key_views[name] = attr
                attrs.pop(name)
                
        attrs['key_views'] = key_views

        return super(ViewCollector, cls).__new__(cls, name, bases, attrs)


class AggregateView(metaclass=ViewCollector):
    @classmethod
    def get_result(cls, key, **kwargs):
        row = {}

        for slug, key_view in cls.key_views.items():
            row[slug] = key_view.get_value(key, **kwargs)

        return row
