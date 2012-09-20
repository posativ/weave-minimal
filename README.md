weave-minimal
=============

This is a lightweight implementation of Mozillas' [User API v1.0][1] and
[Storage API v1.1][2] without LDAP, MySQL, Redis etc. overhead. It is multi
users capable and depends only on [werkzeug][3].

[1]: http://docs.services.mozilla.com/reg/apis.html
[2]: http://docs.services.mozilla.com/storage/apis-1.1.html
[3]: http://werkzeug.pocoo.org/

Setup and Configuration
-----------------------

You need `python` ≥ 2.5 and `werkzeug`. If you use 2.5 also install
`simplejson`. See `python weave.py --help` for a list of parameters including a
short description.

    $> easy_install -U werkzeug
    $> git clone https://github.com/posativ/weave-minimal
    Cloning into weave-minimal...
    $> cd weave-minimal
    $> ./weave.py &
     * Running on http://127.0.0.1:8080/

You can also use `gunicorn` and the `init.d` system to run this service as a
daemon with `invoke-rc.d weave-minimal start`:

```sh
#!/bin/sh
#
# save to /etc/init.d/weave-minimal

NAME=weave-minimal
CHDIR=/path/to/weave-minimal/
USER=weave
CMD=/usr/local/bin/gunicorn
DAEMON_OPTS="-b 127.0.0.1:8014 weave:make_app()"

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

0. **Migrate from the official servers**: write down your mail address and sync
   key (you can reset your password anyway) and unlink your client. If you want
   to keep the previous sync key, enter the key in the advanced settings.

1. **Create a new account** in the sync preferences. Choose a valid mail
   address and password and enter the custom url into the server location
   (leave the trailing slash!). If you get an error, check the SSL certificate
   first.

2. If no errors come up, click continue and wait a minute. If you sync tabs,
   quit, re-open and manually sync otherwise you'll get an empty tab list.

3. **Connect other clients** is as easy as with the mozilla servers (the client
   actually uses mozilla's servers for this): click *I already have an account*
   and write the three codes into an already linked browser using *Pair Device*.
   Optionally you can use the manual prodecure but the you have to enter your
   sync key by hand.

4. If you have connected your clients, you can close the registration by setting
   `ENABLE_REGISTER` to `False` in `controllers/user.py` at the very top.

**Q:** Is this implementation standard compliant?  
**A:** Almost. It works perfectly for me.

**Q:** Is it compatible with the latest version of Firefox?  
**A:** Most times. Compatibility is explicitly denoted as [version
tag](https://github.com/posativ/weave-minimal/tags).

**Q:** Can I use a custom certificate for HTTPS?  
**A:** Yes, but import the CA or visit the url before you enable syncing.
  Firefox will show you a misleading error "invalid url" if you did not accept
  this cert before!

**Q:** It does not sync!?1  
**A:** Did u try turning it off and on again? Your browser, not the server!

### Using a Custom Username

Mozilla assumes, you're using their services, therefore you can not enter a
non-valid email-address and Firefox will prevent you from doing this. But
there's an alternate way:

Instead of entering all your details into the first screen of "Firefox Sync
Setup" you click on "I already have a Firefox Sync Account". Before you can go
to the next step, you have to set up a user account in weave.

    $> ./weave.py --register bob:secret
    [info] database for `bob` created at `.data/bob.e5e9fa1ba31ecd1a`

Now you can continue your Firefox Sync Setup and click "I don't have the device
with me" and enter your username, password, "use custom server" -> url and
secret passphrase. That's all.


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

[4]: http://www.lighttpd.net/

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
