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

from __future__ import print_function

import pkg_resources
dist = pkg_resources.get_distribution("weave-minimal")

try:
    import gevent.monkey; gevent.monkey.patch_all()
except ImportError:
    pass

import sys

if sys.version_info < (2, 7):
    reload(sys)
    sys.setdefaultencoding("utf-8")  # yolo

import os
import errno
import hashlib
import sqlite3
import logging

from os.path import join, dirname
from argparse import ArgumentParser, HelpFormatter, SUPPRESS

try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit

from werkzeug.routing import Map, Rule, BaseConverter
from werkzeug.serving import run_simple
from werkzeug.wrappers import Response
from werkzeug.exceptions import HTTPException, NotFound, NotImplemented

from werkzeug.wsgi import SharedDataMiddleware

from weave.minimal import user, storage, misc
from weave.minimal.utils import encode, Request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s: %(message)s")

logger = logging.getLogger("weave-minimal")


class RegexConverter(BaseConverter):
    def __init__(self, url_map, *items):
        super(RegexConverter, self).__init__(url_map)
        self.regex = items[0]


url_map = Map([
    # reg-server
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>', endpoint=user.index,
         methods=['GET', 'HEAD', 'PUT', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password',
         endpoint=user.change_password, methods=['POST']),
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
         endpoint=misc.captcha_html),
    Rule('/media/<filename>', endpoint=lambda app, env, req: NotImplemented()),

    # info
    Rule('/', endpoint=misc.index),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections',
         endpoint=storage.get_collections_info),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collection_counts',
         endpoint=storage.get_collection_counts),
         Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collection_usage',
              endpoint=storage.get_collection_usage),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/quota',
         endpoint=storage.get_quota),

    # storage
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage',
         endpoint=storage.storage, methods=['DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<cid>',
         endpoint=storage.collection, methods=['GET', 'HEAD', 'PUT', 'POST', 'DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<cid>/<id>',
         endpoint=storage.item, methods=['GET', 'HEAD', 'PUT', 'DELETE']),
], converters={'re': RegexConverter}, strict_slashes=False)


class ReverseProxied(object):
    """
    Handle X-Script-Name and X-Forwarded-Proto. E.g.:

    location /weave {
        proxy_pass http://localhost:8080;
        proxy_set_header X-Script-Name /weave;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    :param app: the WSGI application
    """

    def __init__(self, app, base_url):
        self.app = app
        self.base_url = base_url

    def __call__(self, environ, start_response):

        prefix = None

        if self.base_url is not None:
            scheme, host, prefix, x, y = urlsplit(self.base_url)

            environ['wsgi.url_scheme'] = scheme
            environ['HTTP_HOST'] = host

        if 'HTTP_X_FORWARDED_PROTO' in environ:
            environ['wsgi.url_scheme'] = environ['HTTP_X_FORWARDED_PROTO']

        script_name = environ.get('HTTP_X_SCRIPT_NAME', prefix)
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
        return hashlib.sha1((self.salt+password).encode('utf-8')).hexdigest()[:16]

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

        logger.info("database for `%s` created at `%s`", uid, dbpath)

    def dispatch(self, request, start_response):
        adapter = url_map.bind_to_environ(request.environ)
        try:
            handler, values = adapter.match()
            return handler(self, request.environ, request, **values)
        except NotFound:
            return Response('Not Found', 404)
        except HTTPException as e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch(request, start_response)
        if hasattr(response, 'headers'):
            response.headers['X-Weave-Backoff'] = 0  # we have no load!1
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def make_app(data_dir='.data/', base_url=None, register=False):
    application = Weave(data_dir, register)
    application.wsgi_app = SharedDataMiddleware(application.wsgi_app, {
        "/static": join(dirname(__file__), "static")})
    application.wsgi_app = ReverseProxied(application.wsgi_app, base_url)
    return application


def main():

    fmt = lambda prog: HelpFormatter(prog, max_help_position=28)
    desc = u"A lightweight Firefox Sync server, that just works™. If it " \
           u"doesn't just work for you, please file a bug: " \
           u"https://github.com/posativ/weave-minimal/issues"

    parser = ArgumentParser(description=desc, formatter_class=fmt)
    option = parser.add_argument

    option("--host", dest="host", default="127.0.0.1", type=str,
           metavar="127.0.0.1", help="host interface")
    option("--port", dest="port", default=8080, type=int, metavar="8080",
           help="port to listen on")
    option("--log-file", dest="logfile", default=None, type=str,
           metavar="FILE", help="log to a file")

    option("--data-dir", dest="data_dir", default=".data/", metavar="/var/...",
           help="directory to store sync data, defaults to .data/")
    option("--enable-registration", dest="registration", action="store_true",
           help="enable public registration"),
    option("--base-url", dest="base_url", default=None, metavar="URL",
           help="public URL, e.g. https://example.org/weave/")
    option("--register", dest="creds", default=None, metavar="user:pass",
           help="register a new user and exit")

    option("--use-reloader", action="store_true", dest="reloader",
           help=SUPPRESS, default=False)

    option("--version", action="store_true", dest="version",
           help=SUPPRESS, default=False)

    options = parser.parse_args()

    if options.version:
        print('weave-minimal', dist.version, end=' ')
        print('(Storage API 1.1, User API 1.0)')
        sys.exit(0)

    if options.logfile:
        handler = logging.FileHandler(options.logfile)

        logger.addHandler(handler)
        logging.getLogger('werkzeug').addHandler(handler)

        logger.propagate = False
        logging.getLogger('werkzeug').propagate = False

    app = make_app(options.data_dir, options.base_url, options.registration)

    if options.creds:

        try:
            username, passwd = options.creds.split(':', 1)
        except ValueError:
            logger.error("provide credentials as `user:pass`!")
            sys.exit(os.EX_DATAERR)

        if len(passwd) < 8:
            logger.error("password too short, minimum length is 8")
            sys.exit(os.EX_DATAERR)

        app.initialize(encode(username), passwd)
        sys.exit(os.EX_OK)

    try:
        from gevent.pywsgi import WSGIServer
        WSGIServer((options.host, options.port), app).serve_forever()
    except ImportError:
        run_simple(options.host, options.port, app, use_reloader=options.reloader, threaded=True)


if sys.argv[0].endswith(("gunicorn", "uwsgi")):
    application = make_app(
        data_dir=os.environ.get("DATA_DIR", ".data/"),
        base_url=os.environ.get("BASE_URL", None),
        register=bool(os.environ.get("ENABLE_REGISTRATION", "0")))
