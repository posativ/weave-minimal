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
See `python weave.py --help` for a list of parameters including a short description.

    $> easy_install -U werkzeug
    $> git clone https://github.com/posativ/weave-minimal
    Cloning into weave-minimal...
    $> cd weave-minimal
    $> ./weave.py &
     * Running on http://127.0.0.1:8080/

You can also use `gunicorn` and the `init.d` system to run this service as a daemon
with `invoke-rc.d weave-minimal start`:

```sh
#!/bin/sh
#
# save to /etc/init.d/weave-minimal

NAME=weave-minimal
CHDIR=/home/py/weave-minimal/
USER=py
CMD=/usr/local/bin/gunicorn
DAEMON_OPTS="-b 127.0.0.1:8014 weave:app"

case $1 in
    start)
    echo -n "Starting $NAME: "
    start-stop-daemon --start --pidfile /var/run/$NAME.pid --chdir $CHDIR \
    --chuid $USER --make-pidfile --background --exec $CMD \
    -- $DAEMON_OPTS || true
    echo "$NAME."
       ;;
stop)  start-stop-daemon --stop --pidfile /var/run/$NAME.pid
       ;;
esac
```

Setting up Firefox
------------------

Using a server different from Mozillas' is rather inconvenient but works in
most use-cases. Open the Sync preference pane and choose "Firefox Sync Setup"
-> "Create a new account" and enter your email-address and point to your
`weave-minimal` server. By default everyone can register (I'm too lazy for a
sophisticated registration/captcha method), but you can disable this feature
by setting `ENABLE_REGISTER` to `False`.

Each additional client can connected with the usual procedure (I already have
an account -> connect device -> enter three codes into your other browser).

### Using a Custom Username

Mozilla assumes, you're using their services, therefore you can not enter a
non-valid email-address and Firefox will prevent you from doing this. But there's
an alternate way:

Instead of entering all your details into the first screen of "Firefox Sync Setup"
you click on "I already have a Firefox Sync Account".
Before you can go to the next step, you have to set up a user account in weave.

    $> ./weave.py --register bob:secret
    [info] database for `bob` created at `.data/bob.e5e9fa1ba31ecd1a`

Now you can continue your Firefox Sync Setup and click "I don't have the device with me"
and enter your username, password, "use custom server" -> url and secret passphrase.
That's all.

### Limitations

Write down or save your Firefox Sync key! Neither `weave-minimal` nor Mozilla will
save this and it is (instead of your regular password) your password to decrypt all
data send to the servers.


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

Now, you have to run weave using `./weave.py --prefix=/weave &` to let
weave-minimal recognize that it is served on this specific sub-uri. (This
is an issue of lighttpd itself).

### nginx

Run weave via `./weave.py &` (or inside a `screen`) and add the following to
your nginx.conf:

    location ^~ /weave/ {
        proxy_set_header        Host $host;
        proxy_set_header        X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header        X-Scheme $scheme;
        proxy_set_header        X-Script-Name /weave;
        proxy_pass              http://127.0.0.1:8080;
    }

### other webservers

are possible, but I don't know how to config. Deployment improvements are
always welcome.

[4]: http://www.lighttpd.net/