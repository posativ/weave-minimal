#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug import Response

from os.path import join, isfile
from hashlib import sha1
import sqlite3
import time


def path(dir, user, passwd):
    """return joined path to database using data_dir + '/' + user.sha1(passwd)
    -- a bit truncated though."""
    return join(dir, (user + '.' + sha1(passwd).hexdigest()[:16]))


class login:
    """login decorator using HTTP Digest Authentication. Pattern based on
    http://flask.pocoo.org/docs/patterns/viewdecorators/"""
    
    def __init__(self, methods=['GET', 'POST', 'DELETE', 'PUT']):
        self.methods = methods
    
    def __call__(self, f):

        def dec(env, req, *args, **kwargs):
            """This decorater function will send an authenticate header, if none
            is present and denies access, if HTTP Basic Auth fails."""
            if req.method not in self.methods:
                return f(env, req, *args, **kwargs)
            if not req.authorization:
                response = Response('Unauthorized', 401)
                response.www_authenticate.set_basic('Weave')
                return response
            else:
                user = req.authorization.username
                passwd = req.authorization.password
                if not isfile(path(env['data_dir'], user, passwd)):
                    return Response('Forbidden', 403)
                return f(env, req, *args, **kwargs)
        return dec


def wbo2dict(res):
    """converts sqlite table to WBO (dict [json-parsable])"""
    return {'id': res[0], 'modified': round(res[1], 2),
            'sortindex': res[2], 'payload': res[3], 'ttl': res[4]}
        


_FIELDS = ('id', 'username', 'collection', 'parentid',
           'predecessorid', 'sortindex', 'modified',
           'payload', 'payload_size')


# XXX integrate into storage.py, some copypasta from
# https://hg.mozilla.org/services/server-full/file/962c199ce0f4/1.1/

class WeaveStorage:
    
    def __init__(self, standard_collections=False):
        self.standard_collections = standard_collections
    
    @classmethod
    def iter_collections(self, dbpath):
        """iters all available collection_ids"""
        with sqlite3.connect(dbpath) as db:
            res = db.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        return [x[0] for x in res]
    
    @classmethod
    def get_collection_info(self, dbpath):
        """return the collection names for a given user"""
        
        ids = self.iter_collections(dbpath)
        res = {}
        
        with sqlite3.connect(dbpath) as db:
            for id in ids:
                x = db.execute('SELECT id, MAX(modified) FROM %s;' % id).fetchall()
                for k,v in x:
                    res[id] = round(v, 2)
        return res

    def get_collection(self, dbpath, user_id, collection_name, fields=None):
        """Return information about a collection."""
        if fields is None:
            fields = ['*']
        fields = ', '.join(fields)
        query = ('SELECT %s FROM collections WHERE '
                'userid = %s AND name = %s LIMIT 1') % (fields, user_id, collection_name)
                     
        res = sqlite3.connect(dbpath).execute(query)
        # the collection is created
        if res is None:
            collid = self.set_collection(user_id, collection_name)
            res = {'userid': user_id, 'collectionid': collid,
                   'name': collection_name}
            if fields is not None:
                for key in res.keys():
                    if key not in fields:
                        del res[key]
        else:
            # make this a single step
            res = dict([(key, value) for key, value in res.items()
                         if value is not None])
        return res

    @classmethod
    def set_item(self, dbpath, uid, cid, data):
    
        obj = {'id': data['id']}
        obj['modified'] = data.get('modified', time.time())
        obj['payload'] = data.get('payload', None)
        obj['payload_size'] = len(obj['payload']) if obj['payload'] else 0
        obj['sortindex'] = data.get('sortindex', None)
        obj['ttl'] = data.get('ttl', None)
    
        with sqlite3.connect(dbpath) as db:
            sql = ('main.%s (id VARCHAR(64) PRIMARY KEY, modified FLOAT,'
                   'sortindex INTEGER, payload VARCHAR(256), ttl INTEGER,'
                   'payload_size INTEGER)') % cid
            db.execute("CREATE table IF NOT EXISTS %s;" % sql)
        
            into = []; values = []
            for k,v in obj.iteritems():
                into.append(k); values.append(v)
        
            try:
                db.execute("INSERT INTO %s (%s) VALUES (%s);" % (cid,
                           ', '.join(into), ','.join(['?' for x in values])),
                           values)
            except sqlite3.IntegrityError:
                for k,v in obj.iteritems():
                    if v is None: continue
                    db.execute('UPDATE %s SET %s=? WHERE id=?;' % (cid, k), [v, obj['id']]) 
        return obj
