Couchdbkit aggregate views
==========================

When writing a CouchDB view, one way you might try to structure your map.js
is to emit an associative array of calculated fields:

```javascript
emit([doc.user_id, doc.created_at], {foo: 1, bar: 0})
```

With some work, you can create a reduce.js that sums the values for each
field across all documents, or maybe something a little harder, like
finding the mean.  But if you suddenly need to do something for one field
that can't be done in a CouchDB reduction, like find the median, this
approach fails.

A good way to handle that is to instead do:

```javascript
emit(["foo", doc.user_id, doc.created_at], 1);
emit(["bar", doc.user_id, doc.created_at], 0);
```

That way you can do a CouchDB reduction using the builtin _stats, _count,
or _sum views for fields where you want the sum, mean, etc. and a slower
in-application reduction for fields where you need something more.

In addition, sometimes you want to have some documents not included in the
calculation, but only for one field, such as when a field involves
calculations related to time and you want to exclude documents that aren't
old enough to have a determined value for that field.

Then you could do:

```javascript
emit(["bar", doc.user_id, doc.created_at, doc.some_date], 0);
```

And add another value to your startkey and endkey.

This module attempts to hide some of this complexity by letting you define a
reduce view by doing this in map.js:

```javascript
//!code util/emit_array.js
data = {
    foo: 1,
    bar: 0,
    spam: [1, 1, 2]  // will each be emitted as separate values
};
emit_array([doc.user_id], [doc.created_at], data, {bar: doc.some_date});
```

and this in Python:

```python
from couchdb_aggregate import fn

class MyView(AggregateView):
    foo = KeyView('foo')  # default reduce is built-in couchdb sum
    foo_mean = KeyView('foo', reduce_fn=fn.mean) # using fast _stats view
    fifth_smallest_foo = KeyView('foo,
        reduce_fn=lambda values: sorted(values)[4])
    bar = KeyView('bar', endkey_fn=lambda: today - 4)

result = MyView.view([[user_id1], [user_id2], ...]
                     startkey=[begin_date],
                     endkey=[end_date]
                     db=my_database,
                     couch_view='app/view')

print result
# [ {'foo': sum of foo for user_id1,
     'foo_mean': average foo,
     'bar': sum of bar, but only where doc.some_date < today - 4},
    ...
  ]
```

The KeyView constructor accepts db and couch_view arguments as well, so you
can pull data from multiple views or databases into one combined view if
you want.

This module was developed to make it easier to write simple reports for
[CommCare HQ][1] by using the `[BasicTabularReport][2]` class, which is a thin
wrapper that maps AggregateViews and KeyViews to Reports and Columns and allows
you to define additional views that take in the same keys but get their data
from somewhere other than the database.  See [this HSPH report][3] for an
example.

 [1]: http://github.com/dimagi/commcare-hq
 [2]: https://github.com/dimagi/core-hq/blob/master/corehq/apps/reports/basic.py
 [3]: https://github.com/dimagi/hsph-reports/blob/1c69747d7533b9ec3bc0e00e1f3e272c965dcc84/hsph/reports/call_center.py#L38
