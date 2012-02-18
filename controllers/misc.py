#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug import Response

def captcha_html(environ, request, version):
	return Response('CAPTCHA: set `ENABLE_REGISTER` to True, see controllers/weave.py:30', 200)