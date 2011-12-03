#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug import Response
from os.path import join

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
                try:
                    with file(join(env['data_dir'], user, 'passwd')) as fp:
                        if passwd != fp.read():
                            raise IOError
                except IOError:
                    return Response('Forbidden', 403)
                return f(env, req, *args, **kwargs)
        return dec
