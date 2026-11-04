import os         # only used for os.getenv
import psycopg2   # lets python talk to postgres


# the one place that knows how to reach the database
# api.py and fetcher.py both use this, so the settings are written only once
# everything comes from the environment: .env with compose, the atp-db secret on kubernetes
# host, port, name and user have local defaults, the password on purpose doesn't
def connect():
    password = os.getenv("DB_PASSWORD")
    # no password means something is set up wrong, so stop with a clear message
    # instead of quietly trying a default password that anyone can read on github
    if not password:
        raise RuntimeError("DB_PASSWORD is not set, put it in .env or in the kubernetes secret")

    # the settings are read here and not at the top of the file,
    # so importing this file never needs a database or a password (the CI check relies on that)
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),   # int because environment values always come in as text
        dbname=os.getenv("DB_NAME", "tennis"),
        user=os.getenv("DB_USER", "postgres"),
        password=password,
    )
