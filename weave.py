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
from werkzeug.wsgi import responder

from controllers.user import user, password_reset, change_email
from controllers.storage import get_collections_info, get_collections_count, \
                                get_quota, get_storage, collection, item, index


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
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>', endpoint=user,
         methods=['GET', 'PUT', 'POST', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/node/weave', methods=['GET'],
         endpoint=lambda env,req,version,uid: Response(req.url_root, 200)),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/password_reset',
         endpoint=password_reset, methods=['GET', 'DELETE']),
    Rule('/user/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/email', endpoint=change_email),
    
    # some useless UI stuff, not working, just cop&paste
    Rule('/weave-password-reset', methods=['GET', 'POST'],
         endpoint=lambda env,req: Response('Not Implemented', 501)),
    Rule('/misc/<float:version>/captcha_html',
         endpoint=lambda env,req: Response('Not Implemented', 501)),
    Rule('/media/<filename>', endpoint=lambda env,req: Response('Not Implemented', 501)),
    
    # info
    Rule('/', endpoint=index),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections',
         endpoint=get_collections_info),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/collections_count',
         endpoint=get_collections_count),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/info/quota',
         endpoint=get_quota),
    
    # storage
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/',
         endpoint=get_storage, methods=['PUT', ]),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<re("[a-zA-Z0-9._-]+"):cid>',
         endpoint=collection, methods=['GET', 'PUT', 'POST', 'DELETE']),
    Rule('/<float:version>/<re("[a-zA-Z0-9._-]+"):uid>/storage/<re("[a-zA-Z0-9._-]+"):cid>/<re("[a-zA-Z0-9._-]+"):id>',
         endpoint=item, methods=['GET', 'PUT', 'DELETE']),

], converters={'re': RegexConverter})


@responder
def application(environ, start_response):

    environ['data_dir'] = DATA_DIR
    request = Request(environ)
    urls = url_map.bind_to_environ(environ)
    return urls.dispatch(lambda f, v: f(environ, request, **v),
                         catch_http_exceptions=True)


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
