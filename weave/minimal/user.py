#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import os
import sqlite3

from werkzeug.wrappers import Response

from weave.minimal.utils import login, BadRequest
from weave.minimal.constants import (
    WEAVE_INVALID_WRITE, WEAVE_MISSING_PASSWORD,
    WEAVE_WEAK_PASSWORD, WEAVE_INVALID_USER)


@login(['DELETE', 'POST'])
def index(app, environ, request, version, uid):

    # Returns 1 if the uid is in use, 0 if it is available.
    if request.method in ['HEAD']:
        return Response('', 200)

    elif request.method in ['GET']:
        if not [p for p in os.listdir(app.data_dir) if p.split('.', 1)[0] == uid]:
            code = '0' if app.registration else '1'
        else:
            code = '1'
        return Response(code, 200)

    # Requests that an account be created for uid
    elif request.method == 'PUT':
        if app.registration and not [p for p in os.listdir(app.data_dir) if p.startswith(uid)]:

            try:
                passwd = request.get_json()['password']
            except (KeyError, TypeError):
                raise BadRequest(WEAVE_MISSING_PASSWORD)

            try:
                con = sqlite3.connect(app.dbpath(uid, passwd))
                con.commit()
                con.close()
            except IOError:
                raise BadRequest(WEAVE_INVALID_WRITE)
            return Response(uid, 200)

        raise BadRequest(WEAVE_INVALID_WRITE)

    elif request.method == 'POST':
        return Response('Not Implemented', 501)

    elif request.method == 'DELETE':
        if request.authorization.username != uid:
            return Response('Not Authorized', 401)

        try:
            os.remove(app.dbpath(uid, request.authorization.password))
        except OSError:
            pass
        return Response('0', 200)


@login(['POST'])
def change_password(app, environ, request, version, uid):
    """POST https://server/pathname/version/username/password"""

    if not [p for p in os.listdir(app.data_dir) if p.split('.', 1)[0] == uid]:
        return Response(WEAVE_INVALID_USER, 404)

    if len(request.get_data(as_text=True)) == 0:
        return Response(WEAVE_MISSING_PASSWORD, 400)
    elif len(request.get_data(as_text=True)) < 4:
        return Response(WEAVE_WEAK_PASSWORD, 400)

    old_dbpath = app.dbpath(uid, request.authorization.password)
    new_dbpath = app.dbpath(uid, request.get_data(as_text=True))
    try:
        os.rename(old_dbpath, new_dbpath)
    except OSError:
        return Response(WEAVE_INVALID_WRITE, 503)

    return Response('success', 200)
