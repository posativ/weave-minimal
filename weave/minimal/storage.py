#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys
import math
import time
import json
import sqlite3

if sys.version_info < (2, 7):
    import __builtin__

    class Float(float):

        def __new__(self, x, i):
            self.i = i
            return float.__new__(self, x)

        def __repr__(self):
            return (('%%.%sf' % self.i ) % self)

    defaultround = round
    setattr(__builtin__, 'round', lambda x, i: Float(defaultround(x, 2), i))

from werkzeug import Response

from weave.minimal.utils import login, path, wbo2dict, initialize, convert
from weave.minimal.errors import WeaveException

WEAVE_INVALID_WRITE = "4"         # Attempt to overwrite data that can't be
WEAVE_MALFORMED_JSON = "6"        # Json parse failure
WEAVE_INVALID_WBO = "8"           # Invalid Weave Basic Object
FIELDS = ['id', 'modified', 'sortindex', 'payload', 'parentid', 'predecessorid', 'ttl']


def jsonloads(data):
    data = json.loads(data)
    if not isinstance(data, (dict, list)):
        raise TypeError
    return data


def iter_collections(dbpath):
    """iters all available collection_ids"""
    with sqlite3.connect(dbpath) as db:
        res = db.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
    return [x[0] for x in res]


def expire(dbpath, cid):
    try:
        with sqlite3.connect(dbpath) as db:
            db.execute("DELETE FROM %s WHERE (%s - modified) > ttl" % (cid, time.time()))
    except sqlite3.OperationalError:
        pass


def has_modified(since, dbpath, cid):
    """On any write transaction (PUT, POST, DELETE), if the collection to be acted
    on has been modified since the provided timestamp, the request will fail with
    an HTTP 412 Precondition Failed status."""

    with sqlite3.connect(dbpath) as db:

        try:
            sql = 'SELECT MAX(modified) FROM %s' % cid
            rv = db.execute(sql).fetchone()
        except sqlite3.OperationalError:
            return False

        return rv and since < rv[0]


def set_item(dbpath, uid, cid, data):

    obj = {'id': data['id']}
    obj['modified'] = round(time.time(), 2)
    obj['payload'] = data.get('payload', None)
    obj['payload_size'] = len(obj['payload']) if obj['payload'] else 0
    obj['sortindex'] = data.get('sortindex', None)
    obj['parentid'] = data.get('parentid', None)
    obj['predecessorid'] = data.get('predecessorid', None)
    obj['ttl'] = data.get('ttl', None)

    if obj['sortindex']:
        try:
            obj['sortindex'] = int(math.floor(float(obj['sortindex'])))
        except ValueError:
            return obj

    with sqlite3.connect(dbpath) as db:
        sql = ('main.%s (id VARCHAR(64) PRIMARY KEY, modified FLOAT,'
               'sortindex INTEGER, payload VARCHAR(256),'
               'payload_size INTEGER, parentid VARCHAR(64),'
               'predecessorid VARCHAR(64), ttl INTEGER)') % cid
        db.execute("CREATE table IF NOT EXISTS %s;" % sql)

        into = []; values = []
        for k,v in obj.iteritems():
            into.append(k); values.append(v)

        try:
            db.execute("INSERT INTO %s (%s) VALUES (%s);" % \
                (cid, ', '.join(into), ','.join(['?' for x in values])), values)
        except sqlite3.IntegrityError:
            for k,v in obj.iteritems():
                if v is None: continue
                db.execute('UPDATE %s SET %s=? WHERE id=?;' % (cid, k), [v, obj['id']])
        except sqlite3.InterfaceError:
            raise ValueError

    return obj


@login(['GET', 'HEAD'])
def get_collections_info(app, environ, request, version, uid):
    """Returns a hash of collections associated with the account,
    Along with the last modified timestamp for each collection.
    """
    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    dbpath = path(app.data_dir, uid, request.authorization.password)
    ids = iter_collections(dbpath); collections = {}

    with sqlite3.connect(dbpath) as db:
        for id in ids:
            x = db.execute('SELECT id, MAX(modified) FROM %s;' % id).fetchall()
            for k,v in x:
                if not k:
                    continue # XXX: why None, None yields here?
                collections[id] = round(v, 2)

    return Response(json.dumps(collections), 200, content_type='application/json',
                    headers={'X-Weave-Records': str(len(collections))})


@login(['GET', 'HEAD'])
def get_collection_counts(app, environ, request, version, uid):
    """Returns a hash of collections associated with the account,
    Along with the total number of items for each collection.
    """
    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    dbpath = path(app.data_dir, uid, request.authorization.password)
    ids = iter_collections(dbpath); collections = {}

    with sqlite3.connect(dbpath) as db:
        for id in ids:
            cur = db.execute('SELECT id FROM %s;' % id)
            collections[id] = len(cur.fetchall())

    return Response(json.dumps(collections), 200, content_type='application/json',
                    headers={'X-Weave-Records': str(len(collections))})


@login(['GET', 'HEAD'])
def get_collection_usage(app, environ, request, version, uid):
    """Returns a hash of collections associated with the account, along with
    the data volume used for each (in K).
    """
    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    dbpath = path(app.data_dir, uid, request.authorization.password)
    with sqlite3.connect(dbpath) as db:
        res = {}
        for table in iter_collections(dbpath):
            v = db.execute('SELECT SUM(payload_size) FROM %s' % table).fetchone()
            res[table] = v[0]/1024.0

    js = json.dumps(res)
    return Response(js, 200, content_type='application/json',
                    headers={'X-Weave-Records': str(len(js))})


@login(['GET', 'HEAD'])
def get_quota(app, environ, request, version, uid):
    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    dbpath = path(app.data_dir, uid, request.authorization.password)
    with sqlite3.connect(dbpath) as db:
        sum = 0
        for table in iter_collections(dbpath):
            sum += db.execute('SELECT SUM(payload_size) FROM %s' % table).fetchone()[0] or 0
    # sum = os.path.getsize(dbpath) # -- real usage

    js = json.dumps([sum/1024.0, None])
    return Response(js, 200, content_type='application/json',
                    headers={'X-Weave-Records': str(len(js))})


def storage(app, environ, request, version, uid):

    if request.method == 'DELETE':
        if request.headers.get('X-Confirm-Delete', '0') == '1':
            try:
                initialize(uid, request.authorization.password, app.data_dir)
            except WeaveException, e:
                return Response(str(e), 500)

            return Response(json.dumps(time.time()), 200)

        return Response('Precondition Failed', 412)


@login(['GET', 'HEAD', 'POST', 'PUT', 'DELETE'])
def collection(app, environ, request, version, uid, cid):
    """/<float:version>/<username>/storage/<collection>"""

    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    global FIELDS

    dbpath = path(app.data_dir, uid, request.authorization.password)
    expire(dbpath, cid)

    ids    = request.args.get('ids', None)
    offset = request.args.get('offset', None)
    older  = request.args.get('older', None)
    newer  = request.args.get('newer', None)
    full   = request.args.get('full', False)
    index_above = request.args.get('index_above', None)
    index_below = request.args.get('index_below', None)
    limit  = request.args.get('limit', None)
    offset = request.args.get('offset', None)
    sort   = request.args.get('sort', None)
    parentid = request.args.get('parentid', None)
    predecessorid = request.args.get('predecessorid', None)

    try:
        older and float(older)
        newer and float(newer)
        limit and int(limit)
        offset and int(offset)
        index_above and int(index_above)
        index_below and int(index_below)
    except ValueError:
        return Response(status=400)

    if limit is not None:
        limit = int(limit)

    if offset is not None:
        # we need both
        if limit is None:
            offset = None
        else:
            offset = int(offset)

    if not full:
        fields = ['id']
    else:
        fields = FIELDS

    # filters used in WHERE clause
    filters = {}
    if ids is not None:
        filters['id'] =  'IN', '(%s)' % ids
    if older is not None:
        filters['modified'] = '<', float(older)
    if newer is not None:
        filters['modified'] = '>', float(newer)
    if index_above is not None:
        filters['sortindex'] = '>', int(index_above)
    if index_below is not None:
        filters['sortindex'] = '<', int(index_below)
    if parentid is not None:
        filters['parentid'] = '=', "'%s'" % parentid
    if predecessorid is not None:
        filters['predecessorid'] = '=', "'%s'" % predecessorid

    filter_query, sort_query, limit_query = '', '', ''

    # ORDER BY x ASC|DESC
    if sort is not None:
        if sort == 'index':
            sort_query = ' ORDER BY sortindex DESC'
        elif sort == 'oldest':
            sort_query = ' ORDER BY modified ASC'
        elif sort == 'newest':
            sort_query = ' ORDER BY modified DESC'

    # WHERE x<y AND ...
    if filters:
        filter_query = ' WHERE '
        filter_query += ' AND '.join([k + ' ' + v[0] + ' ' + str(v[1])
            for k, v in filters.iteritems()])

    # LIMIT x [OFFSET y]
    if limit:
        limit_query += ' LIMIT %i' % limit
        if offset:
            limit_query += ' OFFSET %i' % offset

    if request.method == 'GET':
        # Returns a list of the WBO or ids contained in a collection.

        with sqlite3.connect(dbpath) as db:
            try:
                res = db.execute('SELECT %s FROM %s' % (','.join(fields), cid) \
                      + filter_query + sort_query + limit_query).fetchall()
            except sqlite3.OperationalError:
                res = []

        res = [v[0] if len(fields) == 1 else wbo2dict(v) for v in res]
        res, mime, records = convert(res, request.accept_mimetypes.best)

        return Response(res, 200, content_type=mime,
                        headers={'X-Weave-Records': str(records)})

    # before we write, check if the data has not been modified since the request
    since = request.headers.get('X-If-Unmodified-Since', None)
    if since and has_modified(float(since), dbpath, cid):
        return Response('Precondition Failed', 412)

    if request.method == 'DELETE':
        try:
            with sqlite3.connect(dbpath) as db:
                select = 'SELECT id FROM %s' % cid + filter_query \
                       + sort_query + limit_query
                db.execute('DELETE FROM %s WHERE id IN (%s)' % (cid, select))
        except sqlite3.OperationalError:
            pass
        return Response(json.dumps(time.time()), 200)

    elif request.method in ('PUT', 'POST'):

        try:
            data = jsonloads(request.data)
        except ValueError:
            return Response(WEAVE_MALFORMED_JSON, 400)
        except TypeError:
            return Response(WEAVE_INVALID_WBO, 400)

        if isinstance(data, dict):
            data = [data]

        success, failed = [], []
        for item in data:
            if 'id' not in item:
                failed.append(item)
                continue

            try:
                o = set_item(dbpath, uid, cid, item)
                success.append(o['id'])
            except ValueError:
                failed.append(item['id'])

        js = json.dumps({'modified': round(time.time(), 2), 'success': success,
                         'failed': failed})
        return Response(js, 200, content_type='application/json',
                        headers={'X-Weave-Timestamp': round(time.time(), 2)})


@login()
def item(app, environ, request, version, uid, cid, id):
    """GET, PUT or DELETE an item into collection_id."""

    if request.method == 'HEAD' or request.authorization.username != uid:
        return Response('Not Authorized', 401)

    global FIELDS

    dbpath = path(app.data_dir, uid, request.authorization.password)
    expire(dbpath, cid)

    if request.method == 'GET':
        try:
            with sqlite3.connect(dbpath) as db:
                res = db.execute('SELECT %s FROM %s WHERE id=?' % \
                    (','.join(FIELDS), cid), [id]).fetchone()
        except sqlite3.OperationalError:
            # table can not exists, e.g. (not a nice way to do, though)
            res = None

        if res is None:
            return Response(WEAVE_INVALID_WBO, 404)

        js = json.dumps(wbo2dict(res))
        return Response(js, 200, content_type='application/json',
                        headers={'X-Weave-Records': str(len(res))})

    since = request.headers.get('X-If-Unmodified-Since', None)
    if since and has_modified(float(since), dbpath, cid):
        return Response('Precondition Failed', 412)

    if  request.method == 'PUT':
        try:
            data = jsonloads(request.data)
        except ValueError:
            return Response(WEAVE_MALFORMED_JSON, 400)
        except TypeError:
            return Response(WEAVE_INVALID_WBO, 400)

        if id not in data:
            data['id'] = id

        try:
            obj = set_item(dbpath, uid, cid, data)
        except ValueError:
            return Response(WEAVE_INVALID_WBO, 400)

        return Response(json.dumps(obj['modified']), 200,
            content_type='application/json',
            headers={'X-Weave-Timestamp': round(obj['modified'], 2)})

    elif request.method == 'DELETE':
        with sqlite3.connect(dbpath) as db:
            db.execute('DELETE FROM %s WHERE id=?' % cid, [id])
        return Response(json.dumps(time.time()), 200,
            content_type='application/json')
