#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2011 posativ <info@posativ.org>. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
# this list of conditions and the following disclaimer.
#
# 2. Redistributions in binary form must reproduce the above copyright
# notice, this list of conditions and the following disclaimer in the
# documentation and/or other materials provided with the distribution.
#
# The views and conclusions contained in the software and documentation are
# those of the authors and should not be interpreted as representing official
# policies, either expressed or implied, of posativ <info@posativ.org>.

import sys; reload(sys)
sys.setdefaultencoding('utf-8')

from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.wsgi import ClosingIterator
from werkzeug.exceptions import HTTPException, NotFound, NotImplemented

from controllers import user, storage


# set this to a directory of choice
DATA_DIR = '.data/'

# port to listen on 127.0.0.1 (localhost)
PORT = 8080


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


url_map = Map([
    # reg-server
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>', endpoint='user.index',
         methods=['GET', 'PUT', 'POST', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/node/weave', methods=['GET'],
         endpoint=lambda env,req,version,uid: Response(req.url_root, 200)),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password_reset',
         endpoint='user.password_reset', methods=['GET', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/email',
          endpoint='user.change_email'),
    
    # some useless UI stuff, not working, just cop&paste
    Rule('/weave-password-reset', methods=['GET', 'POST'],
         endpoint=lambda env,req: NotImplemented()),
    Rule('/misc/<float:version>/captcha_html',
         endpoint=lambda env,req: NotImplemented()),
    Rule('/media/<filename>', endpoint=lambda env,req: NotImplemented()),

    # info
    Rule('/', endpoint=lambda env,req: NotImplemented()),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections',
         endpoint='storage.get_collections_info'),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections_count',
         endpoint='storage.get_collections_count'),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/quota',
         endpoint='storage.get_quota'),
    
    # storage
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/',
         endpoint='storage.get_storage', methods=['PUT', ]),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<re("[a-zA-Z0-9._-]+"):cid>',
         endpoint='storage.collection', methods=['GET', 'PUT', 'POST', 'DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<re("[a-zA-Z0-9._-]+"):cid>/<re("[a-zA-Z0-9._-]+"):id>',
         endpoint='storage.item', methods=['GET', 'PUT', 'DELETE']),
], converters={'re': RegexConverter})


# stolen from http://flask.pocoo.org/snippets/35/ -- thank you
class ReverseProxied(object):
    '''Wrap the application in this middleware and configure the 
    front-end server to add these headers, to let you quietly bind 
    this to a URL other than / and to an HTTP scheme that is 
    different than what is used locally.

    In nginx:
    location /myprefix {
        proxy_pass http://192.168.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header X-Script-Name /myprefix;
        }

    :param app: the WSGI application
    '''
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        scheme = environ.get('HTTP_X_SCHEME', '')
        if scheme:
            environ['wsgi.url_scheme'] = scheme
        return self.app(environ, start_response)


class Weave(object):
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
    
    def dispatch(self, request, start_response):
        adapter = url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            if hasattr(endpoint, '__call__'):
                handler = endpoint
            else:
                module, function = endpoint.split('.', 1)
                handler = getattr(globals()[module], function)
            return handler(request.environ, request, **values)
        except NotFound, e:
            return Response('Not Found', 404)
        except HTTPException, e:
            return e

    def wsgi_app(self, environ, start_response):
        environ['data_dir'] = self.data_dir
        request = Request(environ)
        response = self.dispatch(request, start_response)
        return response(environ, start_response)
    
    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


application = Weave(DATA_DIR)
application.wsgi_app = ReverseProxied(application.wsgi_app)


if __name__ == '__main__':
    
    if len(sys.argv) == 3 and sys.argv[1] in ['-c', '--register']:
        """quick & dirty user registering; do --register user:pass"""
        
        import os
        import sqlite3
        from utils import path
        
        try:
            user, passwd = sys.argv[2].split(':', 1)
        except ValueError:
            print '[error] provide credentials as `user:pass`!'
            sys.exit(1)
        
        try:
            if not os.path.isdir(DATA_DIR):
                os.mkdir(DATA_DIR)
            else:
                pass
        except OSError:
            print '[error] unable to create directory `%s`' % DATA_DIR
        
        p = path(DATA_DIR, user, passwd)
        with sqlite3.connect(p) as con:
            con.commit()
        print '[info] database for `%s` created at `%s`' % (user, p)
        sys.exit(0)
        
    elif len(sys.argv) == 2 and sys.argv[1] in ['-h', '--help']:
        print '%s [-c --register user:pass]' % sys.argv[0]
        sys.exit(0)
        
    from werkzeug.serving import run_simple
    run_simple('127.0.0.1', PORT, application, use_reloader=True)
