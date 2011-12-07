weave-minimal
=============

This is a lightweight implementation of Mozillas' [User API v1.0][1] and
[Storage API v1.1][2] without LDAP, MySQL, Redis etc. pp. overhead. It has
multi users capabilities and depends on [werkzeug][3] only.

[1]: http://docs.services.mozilla.com/reg/apis.html
[2]: http://docs.services.mozilla.com/storage/apis-1.1.html
[3]: http://werkzeug.pocoo.org/

Setup and Configuration
-----------------------

Make sure you have sqlite available on your system (e.g. `apt-get install libsqlite3-0`)
as well as `python` >= 2.5 (2.5 needs `simplejson` as additional egg though).

    $> easy_install -U werkzeug
    $> git clone https://github.com/posativ/weave-minimal
    Cloning into weave-minimal...
    $> cd weave-minimal
    $> python weave.py --register username:password
    $> python weave.py &
     * Running on http://127.0.0.1:8080/

See `python weave.py --help` for a list of parameters including a short description.


Setting up Firefox
------------------

Using a server different from Mozillas' is rather inconvenient. Instead of
entering all your details into the first screen of "Firefox Sync Setup" you
need to select "I already have a Firefox Sync Account" and click "Connect".

Before you can go to the next step, you need a user account in weave. Firefox
don't let you register a user account on your own server (it's implemented in
weave-minimal, though), so you have to do it on your own.

    $> python weave.py --register bob:secret
    [info] database for `bob` created at `.data/bob.e5e9fa1ba31ecd1a`

Now you can continue your Firefox Sync Setup and click "I don't have the device with me"
and enter your username, password, "use custom server" -> url and secret passphrase.
That's all.


Webserver Configuration
-----------------------

### using lighttpd and mod_proxy

To run weave-minimal using [lighttpd][4] and mod_proxy you need to pass an
extra argument to weave on startup, called `--prefix`. E.g. if you host
weave under `/weave/`, you have at least this basic configuration:

    $HTTP["url"] =~ "^/weave/" {
        proxy.server = ("" =>
           (("host" => "127.0.0.1", "port" => 8080)))
    }

Now, you have to run weave using `python weave.py --prefix=/weave &` to let
weave-minimal recognize that it is served on this specific sub-uri. (This
is an issue of lighttpd itself).

### other webservers

are possible, but I don't know how to config. Deployment improvements are
always welcome.

[4]: http://www.lighttpd.net/