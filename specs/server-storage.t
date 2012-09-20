Test weave-minimal with server-storage test suite.

  $ [ -n "$SERVER_STORAGE" ] || SERVER_STORAGE="/home/py/server-storage"
  $ [ -n "$PYTHON" ] || PYTHON="`which python`"
  $ weave-minimal --port 1234 &> /dev/null &
  $ PID="$!"

Fire!

  $ cd $SERVER_STORAGE
  $ ./bin/python syncstorage/tests/functional/test_storage.py -u test -p test http://127.0.0.1:1234 --create-user &> /dev/null

End this madness.

  $ kill -9 $PID
