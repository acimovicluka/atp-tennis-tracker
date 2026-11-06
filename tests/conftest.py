import os

import pytest
from fastapi.testclient import TestClient

from api import app
from db import connect

# conftest.py is a special file name: pytest reads it by itself before it runs the tests in this folder
# a function marked with @pytest.fixture is something the tests can ask for,
# a test only has to name it as an argument (like def test_ping(client)) and pytest hands it in

# the folder this file is in (tests/) and the main project folder one level above it
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)


# the client fixture builds the test database from scratch: first the real schema.sql, then the made up data from seed.sql
# then it gives back a TestClient, which the api tests use to call the endpoints
# scope="session" means pytest runs this only once, before the first test that needs it, and not before every single test
@pytest.fixture(scope="session")
def client():
    # this fixture drops the tables a few lines below, so it first checks the database name
    # if DB_NAME isn't tennis_test, pytest stops everything, so the tests can never wipe the real database by mistake
    if os.getenv("DB_NAME") != "tennis_test":
        pytest.exit("the api tests only run against a database called tennis_test, set DB_NAME=tennis_test")

    conn = connect()
    cur = conn.cursor()
    # throw away whatever is left from an earlier run, the view first because it depends on the matches table
    cur.execute("DROP VIEW IF EXISTS played_matches")
    cur.execute("DROP TABLE IF EXISTS matches, players")
    # then run schema.sql to make empty tables, and seed.sql to fill them with the test data
    for path in (os.path.join(ROOT_DIR, "schema.sql"), os.path.join(TESTS_DIR, "seed.sql")):
        with open(path, encoding="utf-8") as f:
            cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()

    # TestClient sends requests straight to the app inside python, so the tests need no uvicorn and no open port
    return TestClient(app)
