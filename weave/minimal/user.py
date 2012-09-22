#!/usr/bin/env python
# -*- encoding: utf-8 -*-

WEAVE_ILLEGAL_METH = "1"          # Illegal method/protocol
WEAVE_INVALID_CAPTCHA = "2"       # Incorrect/missing captcha
WEAVE_INVALID_USER = "3"          # Invalid/missing username
WEAVE_INVALID_WRITE = "4"         # Attempt to overwrite data that can't be
WEAVE_WRONG_USERID = "5"          # Userid does not match account in path
WEAVE_MALFORMED_JSON = "6"        # Json parse failure
WEAVE_MISSING_PASSWORD = "7"      # Missing password field
WEAVE_INVALID_WBO = "8"           # Invalid Weave Basic Object
WEAVE_WEAK_PASSWORD = "9"         # Requested password not strong enough
WEAVE_INVALID_RESET_CODE = "10"   # Invalid/missing password reset code
WEAVE_UNSUPPORTED_FUNC = "11"     # Unsupported function
WEAVE_NO_EMAIL_ADRESS = "12"      # No email address on file
WEAVE_INVALID_COLLECTION = "13"   # Invalid collection
WEAVE_OVER_QUOTA = "14"           # User over quota

import os
import sqlite3

try:
    import json
except ImportError:
    import simplejson as json

from werkzeug.wrappers import Response
from weave.minimal.utils import login, path

ENABLE_REGISTER = True

@login(['DELETE', 'POST'])
def index(environ, request, version, uid):

    data_dir = environ['data_dir']

    # Returns 1 if the uid is in use, 0 if it is available.
    if request.method in ['HEAD']:
        return Response('', 200)

    elif request.method in ['GET']:
        if not filter(lambda p: p.split('.', 1)[0] == uid, os.listdir(data_dir)):
            code = '0' if ENABLE_REGISTER else '1'
        else:
            code = '1'
        return Response(code, 200)

    # Requests that an account be created for uid
    elif request.method == 'PUT':
        if not filter(lambda p: p.startswith(uid), os.listdir(data_dir)) and ENABLE_REGISTER:

            try:
                passwd = json.loads(request.data)['password']
            except ValueError:
                return Response(WEAVE_MALFORMED_JSON, 400)
            except KeyError:
                return Response(WEAVE_MISSING_PASSWORD, 400)

            try:
                con = sqlite3.connect(path(data_dir, uid, passwd))
                con.commit()
                con.close()
            except IOError:
                return Response(WEAVE_INVALID_WRITE, 400)
            return Response(uid, 200)

        return Response(WEAVE_INVALID_WRITE, 400)

    elif request.method == 'POST':
        return Response('Not Implemented', 501)

    elif request.method == 'DELETE':
        if request.authorization.username != uid:
            return Response('Not Authorized', 401)

        try:
            os.remove(path(data_dir, uid, request.authorization.password))
        except OSError:
            pass
        return Response('0', 200)


@login(['POST'])
def change_password(environ, request, version, uid):
    """POST https://server/pathname/version/username/password"""

    if not filter(lambda p: p.split('.', 1)[0] == uid, os.listdir(environ['data_dir'])):
        return Response(WEAVE_INVALID_USER, 404)

    if len(request.data) == 0:
        return Response(WEAVE_MISSING_PASSWORD, 400)
    elif len(request.data) < 4:
        return Response(WEAVE_WEAK_PASSWORD, 400)

    old_dbpath = path(environ['data_dir'], uid, request.authorization.password)
    new_dbpath = path(environ['data_dir'], uid, request.data)
    try:
        os.rename(old_dbpath, new_dbpath)
    except OSError:
        return Response(WEAVE_INVALID_WRITE, 503)

    return Response('success', 200)
