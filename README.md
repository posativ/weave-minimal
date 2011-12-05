weave-minimal
=============

This is a lightweight implementation of Mozillas' [User API v1.0][1] and
[Storage API v1.1][2] without LDAP, MySQL, Redis etc. pp. overhead. It has
multi users capabilities and depends on [werkzeug][3] only.

Setup and Configuration
-----------------------

Make sure you have sqlite available on your system (e.g. apt-get install libsqlite3-0)
as well as `python` >= 2.5 (2.5 needs `simplejson` as additional egg though).

    easy_install -U werkzeug
    git clone https://github.com/posativ/weave-minimal
    python weave.py --register username:password
    python weave.py


Webserver Configuration
-----------------------

### using lighttpd and mod_proxy

    $HTTP["url"] =~ "^/weave/" {
        proxy.server = ("" =>
           (("host" => "127.0.0.1", "port" => 8080)))
    }
    
And launch weave-minimal with `python weave.py &`. *Note: currently not working.*