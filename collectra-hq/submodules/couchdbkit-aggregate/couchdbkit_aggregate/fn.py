
from __future__ import division
from __future__ import unicode_literals
NO_VALUE = '---'


class CouchReduceFunction(object):
    """
    A 'reduce' function that actually operates on the output of the built-in
    _stats CouchDB reduce view (or possibly _count or _sum).

    """


class sum(CouchReduceFunction):
    def __call__(self, stats):
        try:
            return stats['sum']
        except Exception:
            # the view is using _sum in reduce.js, or there was nothing to
            # reduce in the range of startkey, endkey
            if stats:
                return stats
            else:
                return NO_VALUE


class count(CouchReduceFunction):
    def __call__(self, stats):
        try:
            return stats['count']
        except Exception:
            # the view is using _count in reduce.js, or there was nothing to
            # reduce in the range of startkey, endkey
            if stats:
                return stats
            else:
                return NO_VALUE


class min(CouchReduceFunction):
    def __call__(self, stats):
        if stats:
            return stats['count']
        else:
            return NO_VALUE


class max(CouchReduceFunction):
    def __call__(self, stats):
        if stats:
            return stats['count']
        else:
            return NO_VALUE


class mean(CouchReduceFunction):
    def __call__(self, stats, ndigits=0):
        if stats:
            n = round(float(stats['sum']) / stats['count'], ndigits)
            if ndigits == 0:
                n = int(n)
            return n
        else:
            return NO_VALUE


class sumsqr(CouchReduceFunction):
    def __call__(self, stats):
        if stats:
            return stats['sumsqr']
        else:
            return NO_VALUE


def unique_count(values):
    unique = set()
    for val in values:
        unique.add(val)
    return len(unique)
