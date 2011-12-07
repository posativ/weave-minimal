#!/usr/bin/env python
# -*- encoding: utf-8 -*-

from werkzeug.test import Client
from weave import make_app
from werkzeug.wrappers import BaseResponse

from werkzeug.test import EnvironBuilder
from base64 import standard_b64encode

application = make_app('.data/')
c = Client(application, BaseResponse)

def test(method, path, data=None, headers={}, auth=None):
    
    if auth:
        headers['Authorization'] = 'Basic %s' % standard_b64encode(auth[0] + ':' + auth[1])
    
    resp = c.open(EnvironBuilder(path, method=method, data=data, headers=headers))
    print method, path, resp.status_code, `resp.data`

if __name__ == '__main__':
        
    test('GET', '/')
    test('GET', '/user/1.0/posativ')
    test('GET', '/user/1.0/other')
    test('PUT', '/user/1.0/posativ', data='{"password": "test"}')
    
    test('GET', '/user/1.0/posativ/node/weave')
    test('GET', '/1.1/posativ/info/collections', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/info/quota')
    
    test('GET', '/1.1/posativ/storage/meta/global')
    test('PUT', '/1.1/posativ/storage/meta/global',
        data='{"payload":"qwertz","id":"global"}')
    test('PUT', '/1.1/posativ/storage/meta/global',
        data='{"payload":"asdf","id":"global", "ttl":"42"}')
    test('POST', '/1.1/posativ/storage/meta',
         data='[{"payload":"asdf","id":"global", "ttl":"42"}, {"payload":"asdf","id":"tmp", "ttl":"42"}]')
    
    test('DELETE', '/1.1/posativ/storage/meta/tmp')
    test('DELETE', '/1.1/posativ/storage/meta')
    test('DELETE', '/1.1/posativ/storage/passwords?id=1,')
    
    test('GET', '/1.1/posativ/info/collections', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/storage/meta/global', auth=('posativ', 'test'))
    
    for i in range(1, 4):
        test('PUT', '/1.1/posativ/storage/test/%s' % i, data='{"payload": "test%s","id":"%s"}' % (i, i))
    test('DELETE', '/1.1/posativ/storage/test?ids=1,3')
    test('GET', '/1.1/posativ/storage/test?ids=1,2&limit=10&sort=index&full=true', auth=('posativ', 'test'))
    test('GET', '/1.1/posativ/storage/test', auth=('posativ', 'test'))
    # XXX not implemented
    test('DELETE', '/user/1.0/posativ', auth=('posativ', 'test'))