from fastapi import FastAPI, HTTPException
import os
import psycopg2


# same settings as in fetcher.py
DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "tennis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "tennis123"),
}

# the whole api hangs off this one object
app = FastAPI(title="ATP tennis tracker")


# first endpoint, just to see the server is up. no db yet
@app.get("/ping")
def ping():
    return {"status": "ok"}


# leftover from testing, can go later
@app.get("/hello")
def hello():
    return {"message": "hello from ATP tracker"}


# first endpoint that actually reads from the db, all above are just for the sake of test
@app.get("/players")
def list_players():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # no LIMIT for now, it's only ~750 players
    cur.execute("SELECT player_id, name, country FROM players ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # rows come back as tuples, turn each one into a dict so the json has field names
    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# one player, the id comes straight from the url
@app.get("/players/{player_id}") # {players} means that code take player_id as ingeteger bsaed on ID thta i want
def get_player(player_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, name, hand, height, country FROM players WHERE player_id = %s",
        (player_id,),
    )
    row = cur.fetchone()
    cur.close()
    conn.close()

    # no such player in the db - say so instead of crashing on row[0]
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")

    return {
        "player_id": row[0],
        "name": row[1],
        "hand": row[2],
        "height": row[3],
        "country": row[4],
    }