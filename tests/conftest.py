import os

import pytest
from fastapi.testclient import TestClient

from api import app
from db import connect

# pytest reads this file by itself before the tests in this folder
# anything marked with @pytest.fixture here can be used by any test, just by naming it as an argument

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(TESTS_DIR)


# fills the test database from scratch: the real schema.sql, then the made up data from seed.sql
# scope="session" means this runs only once, before the first test that needs it, not before every test
@pytest.fixture(scope="session")
def client():
    # the tables get dropped below, so make sure this is never pointed at the real database by mistake
    if os.getenv("DB_NAME") != "tennis_test":
        pytest.exit("the api tests only run against a database called tennis_test, set DB_NAME=tennis_test")

    conn = connect()
    cur = conn.cursor()
    cur.execute("DROP VIEW IF EXISTS played_matches")
    cur.execute("DROP TABLE IF EXISTS matches, players")
    for path in (os.path.join(ROOT_DIR, "schema.sql"), os.path.join(TESTS_DIR, "seed.sql")):
        with open(path, encoding="utf-8") as f:
            cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()

    # TestClient sends requests straight to the app inside python, no uvicorn and no port needed
    return TestClient(app)
