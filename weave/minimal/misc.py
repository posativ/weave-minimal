#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug.wrappers import Response


def index(app, environ, request):
    return Response("It works!", 200)


def captcha_html(app, environ, request, version):
    path = environ.get("HTTP_X_SCRIPT_NAME", "/").rstrip("/")
    return Response("".join([
        '<img src="%s/static/scratch.png" width="298"' % path,
        '     height="130" style="overflow-x: scroll; overflow-y: hidden;"',
        '/>'
    ]), content_type="text/html")
