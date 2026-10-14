from fastapi import FastAPI, HTTPException   # FastAPI builds the app, HTTPException lets us return errors like 404 ourselves
import os         # only used for os.getenv
import psycopg2   # lets python talk to postgres


# same database details as in fetcher.py, both of them talk to the same database
# os.getenv takes the value from the environment if it's set, otherwise the local default on the right
# nothing connects here yet, that happens in psycopg2.connect(**DB) inside each endpoint
DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),   # int because environment values always come in as text
    "dbname": os.getenv("DB_NAME", "tennis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "tennis123"),
}

# the whole api is this one object, every endpoint below gets attached to it
# uvicorn finds it through "api:app", meaning file api.py and variable app
app = FastAPI(title="ATP tennis tracker")   # the title shows up on the /docs page


# checks if a player id exists in the players table and gives back True or False
# this is not an endpoint (no @app.get above it), the endpoints below call it themselves
# it borrows the cursor from the endpoint so it doesn't open a second connection
def player_exists(cur, player_id):
    cur.execute("SELECT 1 FROM players WHERE player_id = %s", (player_id,))   # SELECT 1 because we only care if the row is there, not what's in it
    return cur.fetchone() is not None   # fetchone gives None when nothing was found


# health check, tells you the api is up and running
# docker and kubernetes will call this later to see if the api is still alive
# it doesn't touch the database, so it says ok even when the database is down
@app.get("/ping")
def ping():
    return {"status": "ok"}   # fastapi turns the dict into json by itself


# every player in the database, sorted by name
@app.get("/players")
def list_players():
    conn = psycopg2.connect(**DB)   # open a connection to the database
    cur = conn.cursor()   # the cursor is what sends sql through that connection
    # no LIMIT for now, it's only around 750 players
    cur.execute("SELECT player_id, name, country FROM players ORDER BY name")
    rows = cur.fetchall()   # picks up the result, a list of tuples like ("D643", "Novak Djokovic", "SRB")
    cur.close()
    conn.close()   # always close it, this function runs on every single request

    # tuples only have positions, not names
    # turning each one into a dict gives the json proper field names
    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# search players by part of their name, like /players/search?name=djok
# so nobody has to know ATP ids by heart
# this has to stay ABOVE /players/{player_id}, because fastapi checks the routes from top to bottom
# and would otherwise treat the word "search" as a player id
@app.get("/players/search")
def search_players(name: str):   # name isn't part of the url path, so fastapi takes it from ?name= at the end
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # ILIKE is the same as LIKE but ignores upper and lower case
    # the % on both sides means the text can be anywhere in the name
    cur.execute(
        "SELECT player_id, name, country FROM players WHERE name ILIKE %s ORDER BY name LIMIT 20",
        (f"%{name}%",),   # djok becomes %djok%, it still goes through %s so it's safe
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# one player by ATP id, like /players/D643
@app.get("/players/{player_id}")   # {player_id} is the part of the url that changes, fastapi hands it to the function
def get_player(player_id: str):   # str because ATP ids have letters in them
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT player_id, name, hand, height, country FROM players WHERE player_id = %s",
        (player_id,),   # the comma makes it a tuple with one value, without it this would just be text in brackets
    )
    row = cur.fetchone()   # one row, or None if there's no such player
    cur.close()
    conn.close()

    # no such player, so return 404 instead of crashing on row[0]
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")   # raise stops the function right here

    return {
        "player_id": row[0],
        "name": row[1],
        "hand": row[2],
        "height": row[3],
        "country": row[4],
    }


# wins and losses on every surface for one player, like /players/D643/surface-stats
# the first thing the api actually calculates, it's not written anywhere in the csv
@app.get("/players/{player_id}/surface-stats")
def surface_stats(player_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # a wrong id gives 404 instead of an empty list
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()   # close before raise, because raise stops the function and the close at the bottom would never run
        raise HTTPException(status_code=404, detail="Player not found")
    # FILTER counts only the rows that match the condition, so wins and losses come out in one go
    # GROUP BY makes one row for every surface
    cur.execute(
        """
        SELECT m.surface,
               COUNT(*) FILTER (WHERE m.winner_id = %s) AS wins,
               COUNT(*) FILTER (WHERE m.loser_id = %s) AS losses
        FROM matches m
        WHERE %s IN (m.winner_id, m.loser_id)
        GROUP BY m.surface
        ORDER BY m.surface
        """,
        (player_id, player_id, player_id),   # three %s in the sql, all three are the same player
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # one row per surface: surface, wins, losses
    stats = []
    for row in rows:
        stats.append({"surface": row[0], "wins": row[1], "losses": row[2]})
    return stats


# last 10 matches of one player, newest first, like /players/D643/form
@app.get("/players/{player_id}/form")
def form(player_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")
    # CASE WHEN is the sql version of if/else, it gives W if he won and L if he lost
    # the JOIN brings in the opponent's name from the players table
    # the opponent is the loser if our player won, and the winner if he lost
    # DESC sorts newest first and LIMIT 10 keeps only the last 10
    cur.execute(
        """
        SELECT m.tourney_date,
                m.tourney_name,
                m.surface,
                m.round,
                CASE WHEN m.winner_id = %s THEN 'W' ELSE 'L' END AS result,
                opp.name AS opponent,
                m.score
        FROM matches m
        JOIN players opp
         ON opp.player_id = CASE WHEN m.winner_id = %s THEN m.loser_id ELSE m.winner_id END
        WHERE %s IN (m.winner_id, m.loser_id)
        ORDER BY m.tourney_date DESC, m.match_num DESC
        LIMIT 10
        """,
        (player_id, player_id, player_id),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # one dict per match, row[0] to row[6] follow the order of the columns in the SELECT
    stats = []
    for row in rows:
        stats.append({
            "date": row[0],
            "tournament": row[1],
            "surface": row[2],
            "round": row[3],
            "result": row[4],
            "opponent": row[5],
            "score": row[6],
        })
    return stats


# head to head between two players, like /h2h/D643/S0AG
# gives the overall score and every match they played against each other
@app.get("/h2h/{player1_id}/{player2_id}")
def h2h(player1_id: str, player2_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # both players have to exist, otherwise we'd give back a fake 0:0
    for player_id in (player1_id, player2_id):
        if not player_exists(cur, player_id):
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    # matches where player 1 beat player 2, or player 2 beat player 1
    cur.execute(
        """
        SELECT m.tourney_date, m.tourney_name, m.surface, m.round, m.winner_id, m.score
        FROM matches m
        WHERE (m.winner_id = %s AND m.loser_id = %s)
           OR (m.winner_id = %s AND m.loser_id = %s)
        ORDER BY m.tourney_date DESC, m.match_num DESC
        """,
        (player1_id, player2_id, player2_id, player1_id),   # order matters here, it follows the four %s in the sql
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # count the wins while going through the matches
    player1_wins = 0
    player2_wins = 0
    matches = []
    for row in rows:
        # row[4] is the winner id, whoever won gets the point
        if row[4] == player1_id:
            player1_wins += 1   # += 1 means add one
        else:
            player2_wins += 1   # only these two can be the winner, so else is always player 2

        matches.append({
            "date": row[0],
            "tournament": row[1],
            "surface": row[2],
            "round": row[3],
            "winner_id": row[4],
            "score": row[5],
        })

    # one dict with the score on top and the list of matches under it
    return {
        "player1_id": player1_id,
        "player2_id": player2_id,
        "player1_wins": player1_wins,
        "player2_wins": player2_wins,
        "matches": matches,
    }
