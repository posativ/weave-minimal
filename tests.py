#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import sys

from werkzeug.test import Client
from weave import application
from werkzeug.wrappers import BaseResponse

from werkzeug.test import EnvironBuilder

from base64 import standard_b64encode

builder = EnvironBuilder('/', method='GET')
env = builder.get_environ()

c = Client(application, BaseResponse)

def test(method, path, data=None, headers={}, auth=None):
    
    if auth:
        headers['Authorization'] = 'Basic %s' % standard_b64encode(auth[0] + ':' + auth[1])
    
    resp = c.open(EnvironBuilder(path, method=method, data=data, headers=headers))
    print method, path, resp.status_code, `resp.data`

if __name__ == '__main__':
    
    if not (len(sys.argv) > 1 and sys.argv[1] == '-f'):
        f = True
    else:
        f = False
    
    test('GET', '/')
    test('GET', '/user/1.0/posativ')
    test('GET', '/user/1.0/other')
    test('PUT', '/user/1.0/posativ', data='{"password": "test"}')
    
    test('GET', '/user/1.0/posativ/node/weave')
    test('GET', '/1.1/posativ/info/collections', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/storage/meta/global', auth=('posativ', 'test'))
    if f:
        test('PUT', '/1.1/posativ/storage/meta/global', auth=('posativ', 'test'),
            data='{"payload":"{\\"syncID\\":\\"eKZaDmY-LbUa\\",\\"storageVersion\\":5}","id":"global"}')
        test('PUT', '/1.1/posativ/storage/meta/global', auth=('posativ', 'test'),
            data='{"payload":"{\\"syncID\\":\\"eKZaDmY-LbUa\\",\\"storageVersion\\":5}","id":"global", "ttl":"42"}')
    test('DELETE', '/1.1/posativ/storage/clients', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/info/collections', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/storage/meta/global', auth=('posativ', 'test'))
    if f:
        test('POST', '/1.1/posativ/storage/meta', auth=('posativ', 'test'), data=
            '''[{"payload":"{\\"syncID\\":\\"eKZaDmY-LbUa\\",\\"storageVersion\\":5}","id":"global", "ttl":"42"},
                {"payload":"{lala}","id":"test", "ttl":"23"}]''')
#    test('DELETE', '/user/1.0/posativ', auth=('posativ', 'test'))