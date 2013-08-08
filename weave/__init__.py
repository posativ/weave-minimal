#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2013 Martin Zimmermann <info@posativ.org>. All rights reserved.
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
# policies, either expressed or implied, of Martin Zimmermann <info@posativ.org>.
#
# lightweight firefox weave/sync server

import pkg_resources
dist = pkg_resources.get_distribution("weave-minimal")

import sys; reload(sys)
sys.setdefaultencoding('utf-8')

import os
import errno
import hashlib
import sqlite3

from os.path import join
from optparse import OptionParser, make_option, SUPPRESS_HELP
from urlparse import urlsplit

from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, NotFound, NotImplemented, InternalServerError

from weave.minimal import user, storage, misc
from weave.minimal.utils import encode

try:
    import bjoern
except ImportError:
    bjoern = None  # NOQA


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


url_map = Map([
    # reg-server
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>', endpoint='user.index',
         methods=['GET', 'HEAD', 'PUT', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password',
         endpoint='user.change_password', methods=['POST']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/node/weave',
         endpoint=lambda app, env, req, version, uid: Response(req.url_root, 200)),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password_reset',
         endpoint=lambda *args, **kw: NotImplemented()),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/email',
          endpoint=lambda *args, **kw: NotImplemented()),

    # some useless UI stuff, not working
    Rule('/weave-password-reset', methods=['GET', 'HEAD', 'POST'],
         endpoint=lambda app, env, req: NotImplemented()),
    Rule('/misc/<float:version>/captcha_html',
         endpoint='misc.captcha_html'),
    Rule('/media/<filename>', endpoint=lambda app, env, req: NotImplemented()),

    # info
    Rule('/', endpoint=lambda app, env, req: NotImplemented()),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections',
         endpoint='storage.get_collections_info'),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collection_counts',
         endpoint='storage.get_collection_counts'),
         Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collection_usage',
              endpoint='storage.get_collection_usage'),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/quota',
         endpoint='storage.get_quota'),

    # storage
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage',
         endpoint='storage.storage', methods=['DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<cid>',
         endpoint='storage.collection', methods=['GET', 'HEAD', 'PUT', 'POST', 'DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<cid>/<id>',
         endpoint='storage.item', methods=['GET', 'HEAD', 'PUT', 'DELETE']),
], converters={'re': RegexConverter}, strict_slashes=False)


# stolen from http://flask.pocoo.org/snippets/35/ -- thank you, but does not
# work for lighttpd (server issue, fixed in 1.5, not released yet), use --prefix="/myprefix" instead
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
    def __init__(self, app, prefix, base_url):
        self.app = app
        self.prefix = prefix
        self.base_url = base_url

    def __call__(self, environ, start_response):

        if self.base_url is not None:
            scheme, host, prefix, x, y = urlsplit(self.base_url)

            environ['wsgi.url_scheme'] = scheme
            environ['HTTP_HOST'] = host

            self.prefix = prefix

        if 'HTTP_X_SCHEME' in environ:
            environ['wsgi.url_scheme'] = environ['HTTP_X_SCHEME']

        script_name = environ.get('HTTP_X_SCRIPT_NAME', self.prefix)
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ['PATH_INFO']
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]

        return self.app(environ, start_response)


class Weave(object):

    salt = r'\x14Q\xd4JbDk\x1bN\x84J\xd0\x05\x8a\x1b\x8b\xa6&V\x1b\xc5\x91\x97\xc4'

    def __init__(self, data_dir, registration):

        try:
            os.makedirs(data_dir)
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise

        self.data_dir = data_dir
        self.registration = registration

    def crypt(self, password):
        return hashlib.sha1(self.salt+password).hexdigest()[:16]

    def dbpath(self, user, password):
        return join(self.data_dir, (user + '.' + self.crypt(password)))

    def initialize(self, uid, password):

        dbpath = self.dbpath(uid, password)

        try:
            os.unlink(dbpath)
        except OSError:
            pass

        with sqlite3.connect(dbpath) as con:
            con.commit()

        print '[info] database for `%s` created at `%s`' % (uid, dbpath)


    def dispatch(self, request, start_response):
        adapter = url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            if hasattr(endpoint, '__call__'):
                handler = endpoint
            else:
                module, function = endpoint.split('.', 1)
                handler = getattr(globals()[module], function)
            return handler(self, request.environ, request, **values)
        except NotFound, e:
            return Response('Not Found', 404)
        except HTTPException, e:
            return e
        except InternalServerError, e:
            return Response(e, 500)

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch(request, start_response)
        if hasattr(response, 'headers'):
            response.headers['X-Weave-Backoff'] = 0  # we have no load!1
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def make_app(data_dir='.data/', prefix=None, base_url=None, register=False):
    application = Weave(data_dir, register)
    application.wsgi_app = ReverseProxied(application.wsgi_app, prefix, base_url)
    return application


def main():

    options = [
        make_option("--data-dir", dest="data_dir", default=".data/",
                    help="data directory to store user profile"),
        make_option("--host", dest="host", default="127.0.0.1", type=str,
                    help=SUPPRESS_HELP),
        make_option("--port", dest="port", default=8080, type=int,
                    help="port to serve on"),
        make_option("--register", dest="creds", default=None,
                    help="user:passwd credentials"),
        make_option("--enable-registration", dest="registration", action="store_true",
                    help="enable registration"),
        make_option("--prefix", dest="prefix", default="/",
                    help="prefix support for broken servers, deprecated."),
        make_option("--base-url", dest="base_url", default=None,
                    help="set your actual URI such as https://example.org/weave/"),
        make_option("--use-reloader", action="store_true", dest="reloader",
                    help=SUPPRESS_HELP, default=False),
        make_option("--version", action="store_true", dest="version",
                    help=SUPPRESS_HELP, default=False),
        ]

    parser = OptionParser(option_list=options)
    (options, args) = parser.parse_args()

    if options.version:
        print 'weave-minimal', dist.version,
        print '(Storage API 1.1, User API 1.0)'
        sys.exit(0)

    prefix = options.prefix.rstrip('/')
    app = make_app(options.data_dir, prefix, options.base_url, options.registration)

    if options.creds:

        try:
            username, passwd = options.creds.split(':', 1)
        except ValueError:
            print '[error] provide credentials as `user:pass`!'
            sys.exit(1)

        app.initialize(encode(username), passwd, options.data_dir)

    elif bjoern and not options.reloader:
        print ' * Running on http://%s:%s/ using bjoern' % (options.host, options.port)
        bjoern.run(app, options.host, options.port)
    else:
        run_simple(options.host, options.port, app,
                   use_reloader=options.reloader, threaded=True)
