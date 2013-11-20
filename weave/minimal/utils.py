#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import pkg_resources
werkzeug = pkg_resources.get_distribution("werkzeug")

import re
import json
import base64
import struct

from os.path import isfile
from hashlib import sha1

from werkzeug.wrappers import Request as _Request, Response
from werkzeug.exceptions import BadRequest as _BadRequest

from weave.minimal.compat import iterkeys
from weave.minimal.constants import WEAVE_MALFORMED_JSON, WEAVE_INVALID_WBO


class BadRequest(_BadRequest):
    """Remove fancy HTML from exceptions."""

    def get_headers(self, environ):
        return [("Content-Type", "text/plain")]

    def get_body(self, environ):
        return self.description


class Request(_Request):

    max_content_length = 512 * 1024

    if werkzeug.version.startswith("0.8"):
        def get_data(self, **kw):
            return self.data.decode('utf-8')

    def get_json(self):
        try:
            data = json.loads(self.get_data(as_text=True))
        except ValueError:
            raise BadRequest(WEAVE_MALFORMED_JSON)
        else:
            if not isinstance(data, (dict, list)):
                raise BadRequest(WEAVE_INVALID_WBO)
            return data


def encode(uid):
    if re.search('[^A-Z0-9._-]', uid, re.I):
        return base64.b32encode(sha1(uid).digest()).lower()
    return uid


class login:
    """login decorator using HTTP Basic Authentication. Pattern based on
    http://flask.pocoo.org/docs/patterns/viewdecorators/"""

    def __init__(self, methods=['GET', 'POST', 'DELETE', 'PUT']):
        self.methods = methods

    def __call__(self, f):

        def dec(app, env, req, *args, **kwargs):
            """This decorater function will send an authenticate header, if none
            is present and denies access, if HTTP Basic Auth fails."""
            if req.method not in self.methods:
                return f(app, env, req, *args, **kwargs)
            if not req.authorization:
                response = Response('Unauthorized', 401)
                response.www_authenticate.set_basic('Weave')
                return response
            else:
                user = req.authorization.username
                passwd = req.authorization.password
                if not isfile(app.dbpath(user, passwd)):
                    return Response('Unauthorized', 401)  # kinda stupid
                return f(app, env, req, *args, **kwargs)
        return dec


def wbo2dict(query):
    """converts sqlite table to WBO (dict [json-parsable])"""

    res = {'id': query[0], 'modified': round(query[1], 2),
           'sortindex': query[2], 'payload': query[3],
           'parentid': query[4], 'predecessorid': query[5], 'ttl': query[6]}

    for key in list(iterkeys(res)):
        if res[key] is None:
            res.pop(key)

    return res


def convert(value, mime):
    """post processor producing lists in application/newlines format."""

    if mime and mime.endswith(('/newlines', '/whoisi')):
        try:
            value = value["items"]
        except (KeyError, TypeError):
            pass

        if mime.endswith('/whoisi'):
            res = []
            for record in value:
                js = json.dumps(record)
                res.append(struct.pack('!I', len(js)) + js.encode('utf-8'))
            rv = b''.join(res)
        else:
            rv = '\n'.join(json.dumps(item).replace('\n', '\000a') for item in value)
    else:

        rv, mime = json.dumps(value), 'application/json'

    return rv, mime, len(value)
