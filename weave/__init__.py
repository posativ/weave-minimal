#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright 2012 posativ <info@posativ.org>. All rights reserved.
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
#
# lightweight firefox weave/sync server

__version__ = '0.15.3'

import sys; reload(sys)
sys.setdefaultencoding('utf-8')

from optparse import OptionParser, make_option, SUPPRESS_HELP

from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.serving import run_simple
from werkzeug.wrappers import Request, Response
from werkzeug.exceptions import HTTPException, NotFound, NotImplemented, InternalServerError

from weave.minimal import user, storage, misc
from weave.minimal.utils import encode, initialize
from weave.minimal.errors import WeaveException


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
         endpoint=lambda env,req,version,uid: Response(req.url_root, 200)),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password_reset',
         endpoint=lambda *args, **kw: NotImplemented()),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/email',
          endpoint=lambda *args, **kw: NotImplemented()),

    # some useless UI stuff, not working
    Rule('/weave-password-reset', methods=['GET', 'HEAD', 'POST'],
         endpoint=lambda env,req: NotImplemented()),
    Rule('/misc/<float:version>/captcha_html',
         endpoint='misc.captcha_html'),
    Rule('/media/<filename>', endpoint=lambda env,req: NotImplemented()),

    # info
    Rule('/', endpoint=lambda env,req: NotImplemented()),
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
], converters={'re': RegexConverter})


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
    def __init__(self, app, prefix):
        self.app = app
        self.prefix = prefix if prefix is not None else ''

    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', self.prefix)
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
        except InternalServerError, e:
            return Response(e, 500)

    def wsgi_app(self, environ, start_response):
        environ['data_dir'] = self.data_dir
        request = Request(environ)
        response = self.dispatch(request, start_response)
        if hasattr(response, 'headers'):
            response.headers['X-Weave-Backoff'] = 0  # we have no load!1
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def make_app(data_dir='.data/', prefix=None):
    application = Weave(data_dir)
    application.wsgi_app = ReverseProxied(application.wsgi_app, prefix=prefix)
    return application


def main():

    options = [
        make_option("-d", dest="data_dir", default=".data/",
                    help="data directory to store user profile"),
        make_option("-p", "--port", dest="port", default=8080, type=int,
                    help="port to serve on"),
        make_option("--register", dest="creds", default=None,
                    help="user:passwd credentials"),
        make_option("--prefix", dest="prefix", default="/",
                    help="prefix support for broken server, e.g. lighttpd 1.4.x"),
        make_option("--use-reloader", action="store_true", dest="reloader",
                    help=SUPPRESS_HELP, default=False),
        make_option("--version", action="store_true", dest="version",
                    help=SUPPRESS_HELP, default=False),
        ]

    parser = OptionParser(option_list=options)
    (options, args) = parser.parse_args()

    if options.version:
        print __version__
        sys.exit(0)

    if options.creds:
        """user registration via --register user:pass"""

        try:
            username, passwd = options.creds.split(':', 1)
        except ValueError:
            print '[error] provide credentials as `user:pass`!'
            sys.exit(1)

        try:
            initialize(encode(username), passwd, options.data_dir)
        except WeaveException:
            sys.exit(1)
        sys.exit(0)

    prefix = options.prefix.rstrip('/')
    run_simple('127.0.0.1', options.port, make_app(options.data_dir, prefix),
               use_reloader=options.reloader)
