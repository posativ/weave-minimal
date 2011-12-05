#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug import Response
from utils import login, WeaveStorage, path
import sqlite3, time

try:
    import json
except ImportError:
    import simplejson as json

WEAVE_INVALID_WRITE = "4"
WEAVE_MALFORMED_JSON = "6"        # Json parse failure
_WBO_FIELDS = ['id', 'parentid', 'predecessorid', 'sortindex', 'modified',
               'payload', 'payload_size']
storage = WeaveStorage()

@login(['GET', ])
def get_collections_info(environ, request, version, uid):
    """Returns a hash of collections associated with the account,
    Along with the last modified timestamp for each collection
    """
    passwd = request.authorization.password
    dbpath = path(environ['data_dir'], uid, passwd)

    collections = storage.get_collection_info(dbpath)
    return Response(json.dumps(collections), 200, content_type='application/json; charset=utf-8',
                    headers={'X-Weave-Records': str(len(collections))})

@login(['GET', ])
def get_collections_count(environ, request, version, uid):
    """Returns a hash of collections associated with the account,
    Along with the total number of items for each collection.
    """
    counts = storage.get_collection_counts(environ['data_dir'], uid)
    return Response(json.dumps({}), 200, content_type='application/json; charset=utf-8',
                    headers={'X-Weave-Records': str(len(counts))})

@login(['GET', ])
def get_quota():
    return Response('Not Implemented', 501)

def get_storage(environ, request, version, uid):
    # XXX returns a 400 if the root is called # -- WTF?
    return Response(status_code=400)

def collection(environ, request, version, uid, cid):
    """/<float:version>/<uid>/storage/<collection>"""
    
    dbpath = path(environ['data_dir'], uid, request.authorization.password)
    form = request.form
    
    ids = form.get('ids', None)
    predecessorid = form.get('predecessorid', None)
    parentid = form.get('parentid', None)
    older = form.get('older', None)
    newer = form.get('newer', None)
    full = form.get('full', False)
    index_above = form.get('index_above', None)
    index_below = form.get('index_below', None)
    limit = form.get('limit', None)
    offset = form.get('offset', None)
    sort = form.get('sort', None)
    
    # XXX sanity check on arguments (detect incompatible params here, or
    # unknown values)
    filters = {}
    if ids is not None:
        ids = [int(id_) for id_ in ids.split(',')]
        filters['id'] = 'in', ids
    if predecessorid is not None:
        filters['predecessorid'] = '=', predecessorid
    if parentid is not None:
        filters['parentid'] = '=', parentid
    if older is not None:
        filters['modified'] = '<', older
    if newer is not None:
        filters['modified'] = '>', newer
    if index_above is not None:
        filters['sortindex'] = '>', float(index_above)
    if index_below is not None:
        filters['sortindex'] = '<', float(index_below)

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
        fields = _WBO_FIELDS

    
    """Returns a list of the WBO ids contained in a collection."""
    if request.method == 'GET':
        # 
        # res = storage.get_items(uid, cid, fields, filters, limit, offset, sort)
        # if not full:
        #     res = [line['id'] for line in res]
        

        return Response(res, 200, content_type='application/json; charset=utf-8',
                        headers={'X-Weave-Records': str(len(res))})
                        
    elif request.method == 'POST':
        try:
            data = json.loads(request.data)
        except ValueError:
            return Response(WEAVE_MALFORMED_JSON, 200)

        success = []
        for item in data:
            o = storage.set_item(dbpath, uid, cid, item)
            success.append(o['id'])

        # XXX guidance as to possible errors (?!)
        js = json.dumps({'modified': round(time.time(), 2), 'success': success})
        return Response(js, 200, content_type='application/json; charset=utf-8',
                        headers={'X-Weave-Records': str(len(js))})
                        
    elif request.method == 'DELETE':
        # print `request.data`
        # print `request.args`
        with sqlite3.connect(dbpath) as db:
            # XXX implement offset
            if ids is not None:
                ids = ids.split(',')
                db.execute('DELETE * FROM %s WHERE id IN (%s);' % (cid, ids))
            else:
                db.execute('DROP table IF EXISTS %s' % cid)
        return Response('', 200)

@login()
def item(environ, request, version, uid, cid, id):
    
    dbpath = path(environ['data_dir'], uid, request.authorization.password)
    
    if request.method == 'GET':
        try:
            with sqlite3.connect(dbpath) as db:
                res = db.execute('SELECT * FROM %s WHERE id=?' % cid, [id]).fetchone()
        except sqlite3.OperationalError:
            res = None
        
        if res is None:
            return Response('Not Found', 404)
        
        js = json.dumps({'id': res[0], 'modified': round(res[1], 2),
                         'sortindex': res[2], 'payload': res[3], 'ttl': res[4]})
        return Response(js, 200, content_type='application/json; charset=utf-8',
                        headers={'X-Weave-Records': str(len(js))})
    
    elif request.method == 'PUT':
        try:
            data = json.loads(request.data)
        except ValueError:
            return Response(WEAVE_MALFORMED_JSON, 200)
        
        if id != data['id']:
            return Response(WEAVE_INVALID_WRITE, 400)

        obj = storage.set_item(dbpath, uid, cid, data)
        js = json.dumps(obj)
        return Response(js, 200, content_type='application/json; charset=utf-8',
                        headers={'X-Weave-Records': str(len(js))})
    
    elif request.method == 'DELETE':
        # XXX request parameters like passwords?ids={337b9bcd-d96e-ea41-960b-fceeee75b6f7},{0bec633d-a15f-aa4a-9b79-f5b793d6dd18}
        with sqlite3.connect(dbpath) as db:
            db.execute('DELETE * FROM %s WHERE id=?' % cid, [id])
        return Response('Deleted', 200)

def index(environ, request):
    return Response('Not Implemented', 501)
