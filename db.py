import os         # only needed for os.getenv, which reads environment variables
import psycopg2   # the library python uses to talk to postgres, it sends the sql and brings back the results


# connect() is the one place in the project that knows how to reach the database
# api.py, fetcher.py and the tests all import it, so the settings are written only once
# before this file existed, api.py and fetcher.py each had their own copy, and a change in one was easy to forget in the other
#
# the settings themselves are not in the code, they come from environment variables
# whoever starts the program sets them: compose takes them from .env, kubernetes from the atp-db secret, CI from ci.yml
# that way the same code runs everywhere and the password never ends up on github
def connect():
    password = os.getenv("DB_PASSWORD")
    # the password has no default on purpose
    # if it's missing, something is set up wrong, so the function stops right away with a clear message (fail fast)
    # the old version quietly tried tennis123, and anyone could read that password on github
    if not password:
        raise RuntimeError("DB_PASSWORD is not set, put it in .env or in the kubernetes secret")

    # connect() reads the settings here, when someone calls it, and not at the top of the file
    # so python can import this file (and api.py and fetcher.py) without a database or a password,
    # and the tests rely on that
    # host, port, name and user have local defaults, the second value in os.getenv is used when the variable isn't set
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),   # db in compose and kubernetes (the service name), localhost on my computer and in CI
        port=int(os.getenv("DB_PORT", 5432)),   # environment variables always come in as text, int turns "5432" into the number 5432
        dbname=os.getenv("DB_NAME", "tennis"),
        user=os.getenv("DB_USER", "postgres"),
        password=password,
    )
