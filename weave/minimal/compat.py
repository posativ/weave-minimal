# -*- encoding: utf-8 -*-
#
# Copyright 2013 Armin Ronacher <armin.ronacher@active-4.com>. All rights reserved.
# License: BSD Style, 2 clauses -- see LICENSE.
#
# http://lucumr.pocoo.org/2013/5/21/porting-to-python-3-redux/

import sys
PY2K = sys.version_info[0] == 2

if not PY2K:
    iterkeys = lambda d: iter(d.keys())
    iteritems = lambda d: iter(d.items())
else:
    iterkeys = lambda d: d.iterkeys()
    iteritems = lambda d: d.iteritems()
