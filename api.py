# api.py is the api: it reads from the database and answers in json
# every function with @app.get above it is one endpoint, one address you can open in the browser
# uvicorn starts it and keeps it running, and /docs shows a page with every endpoint where you can try them out

from fastapi import FastAPI, HTTPException   # FastAPI builds the app, HTTPException lets the api answer with errors like 404
from fastapi.responses import JSONResponse   # lets /ready answer with whatever status code I pick
from prometheus_fastapi_instrumentator import Instrumentator   # counts the requests so prometheus can read them

from db import connect   # the function from db.py that opens the database connection

# app is the whole api, every endpoint below gets attached to it
# uvicorn finds it through "api:app", which means the file api.py and the variable app inside it
app = FastAPI(title="ATP tennis tracker")   # the title shows up at the top of the /docs page

# the instrumentator adds a /metrics address, and prometheus reads it every 15 seconds
# for every request it counts which endpoint was called, what status code came back and how long it took
# it leaves out /ping, /ready and /metrics: kubernetes calls the first two every few seconds,
# and prometheus calls the third one, so they would drown out the real traffic
Instrumentator(excluded_handlers=["/ping", "/ready", "/metrics"]).instrument(app).expose(app)


# player_exists checks if a player id is in the players table and gives back True or False
# it's not an endpoint (there's no @app.get above it), the endpoints below call it themselves
# it borrows the cursor from the endpoint, so it doesn't have to open a second connection
def player_exists(cur, player_id):
    cur.execute("SELECT 1 FROM players WHERE player_id = %s", (player_id,))   # SELECT 1 because I only care if the row is there, not what's in it
    return cur.fetchone() is not None   # fetchone gives back None when postgres found nothing


# /ping is the health check, it only says the api process is up and answering
# kubernetes calls it for the liveness probe, and if it stops answering kubernetes restarts the pod
# it doesn't touch the database on purpose: if the database is down, restarting the api wouldn't fix anything
@app.get("/ping")
def ping():
    return {"status": "ok"}   # fastapi turns the dict into json by itself


# /ready is the readiness check, it says the api can actually do its job, which means it can reach the database
# kubernetes calls it for the readiness probe: while it fails, kubernetes sends no traffic to this pod, but doesn't restart it
# 503 means "service unavailable", the usual way to say "I'm running, but I can't serve anything right now"
@app.get("/ready")
def ready():
    try:
        conn = connect()
        cur = conn.cursor()
        cur.execute("SELECT 1")   # the smallest question you can ask, it only checks that the database answers
        cur.close()
        conn.close()
    except Exception:   # if anything above fails (no connection, wrong password, database down), the api answers with 503
        return JSONResponse(status_code=503, content={"status": "database unavailable"})
    return {"status": "ok"}


# /players gives back every player in the database, sorted by name
# every endpoint below follows the same steps: connect, send the sql, pick up the result, close, build the json
@app.get("/players")
def list_players():
    conn = connect()   # opens a connection to the database
    cur = conn.cursor()   # the cursor is what the api uses to send sql through that connection
    # no LIMIT for now, there are only around 850 players
    cur.execute("SELECT player_id, name, country FROM players ORDER BY name")
    rows = cur.fetchall()   # picks up the whole result, a list of tuples like ("D643", "Novak Djokovic", "SRB")
    cur.close()
    conn.close()   # always close it, this function runs on every single request and open connections pile up

    # a tuple only has positions (row[0], row[1]...), not names
    # so the api turns each one into a dict, and the json gets proper field names like "name" and "country"
    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# /players/search finds players by part of their name, like /players/search?name=djok
# so nobody has to know the ATP ids by heart
# it has to stay ABOVE /players/{player_id}: fastapi checks the routes from top to bottom,
# and otherwise it would think the word "search" is a player id
@app.get("/players/search")
def search_players(name: str):   # name isn't part of the path, so fastapi takes it from the ?name= at the end of the url
    conn = connect()
    cur = conn.cursor()
    # ILIKE works like LIKE but doesn't care about upper and lower case
    # the % on both sides means the text can be anywhere in the name
    # unaccent removes accents on both sides, so "ković" finds "Kovic"
    # đ is the one letter unaccent gets wrong for us: it turns it into d, but the names in the data use dj (Djokovic, Djere)
    # so the api swaps đ for dj first, and then "đok" finds Djokovic too
    name = name.replace("đ", "dj").replace("Đ", "Dj")
    cur.execute(
        "SELECT player_id, name, country FROM players WHERE unaccent(name) ILIKE unaccent(%s) ORDER BY name LIMIT 20",
        (f"%{name}%",),   # djok becomes %djok%, and it still goes in through %s, so psycopg2 keeps it safe from sql injection
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# /players/{player_id} gives back one player by his ATP id, like /players/D643
@app.get("/players/{player_id}")   # {player_id} is the part of the url that changes, fastapi passes it to the function
def get_player(player_id: str):   # str because ATP ids have letters in them
    conn = connect()
    cur = conn.cursor()
    # %s is an empty spot that psycopg2 fills in safely, the api never glues the id straight into the sql text
    cur.execute(
        "SELECT player_id, name, hand, height, country FROM players WHERE player_id = %s",
        (player_id,),   # the comma makes it a tuple with one value, without it python would see plain text in brackets
    )
    row = cur.fetchone()   # one row, or None if there's no player with that id
    cur.close()
    conn.close()

    # no such player, so the api answers with 404 instead of crashing on row[0]
    if row is None:
        raise HTTPException(status_code=404, detail="Player not found")   # raise stops the function right here

    return {
        "player_id": row[0],
        "name": row[1],
        "hand": row[2],
        "height": row[3],
        "country": row[4],
    }


# /players/{player_id}/surface-stats gives wins and losses on every surface for one player, like /players/D643/surface-stats
# this was the first thing the api actually calculates itself, it isn't written anywhere in the csv
@app.get("/players/{player_id}/surface-stats")
def surface_stats(player_id: str):
    conn = connect()
    cur = conn.cursor()
    # with a wrong id the api answers with 404, and not with an empty list that looks like a player with no matches
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()   # close before raise, because raise stops the function and the close at the bottom would never run
        raise HTTPException(status_code=404, detail="Player not found")
    # FILTER tells COUNT to count only the rows that match the condition, so wins and losses come out of one query
    # GROUP BY makes one row for every surface
    # the api reads from played_matches, which is the matches table without walkovers (see schema.sql)
    cur.execute(
        """
        SELECT m.surface,
               COUNT(*) FILTER (WHERE m.winner_id = %s) AS wins,
               COUNT(*) FILTER (WHERE m.loser_id = %s) AS losses
        FROM played_matches m
        WHERE %s IN (m.winner_id, m.loser_id)
        GROUP BY m.surface
        ORDER BY m.surface
        """,
        (player_id, player_id, player_id),   # there are three %s in the sql, and all three are the same player
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # one dict for every surface: the surface, the wins and the losses
    stats = []
    for row in rows:
        stats.append({"surface": row[0], "wins": row[1], "losses": row[2]})
    return stats


# /players/{player_id}/form gives the last 10 matches of one player, newest first, like /players/D643/form
@app.get("/players/{player_id}/form")
def form(player_id: str):
    conn = connect()
    cur = conn.cursor()
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")
    # CASE WHEN is the sql version of if/else, it gives W if our player won and L if he lost
    # the JOIN connects the match to the players table, so the api gets the opponent's name and not just his id
    # the opponent is the loser if our player won, and the winner if he lost, that's what the second CASE WHEN picks
    # DESC sorts newest first, and LIMIT 10 keeps only the last 10
    cur.execute(
        """
        SELECT m.tourney_date,
                m.tourney_name,
                m.surface,
                m.round,
                CASE WHEN m.winner_id = %s THEN 'W' ELSE 'L' END AS result,
                opp.name AS opponent,
                m.score
        FROM played_matches m
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

    # one dict for every match, row[0] to row[6] follow the order of the columns in the SELECT above
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


# /h2h/{player1_id}/{player2_id} is the head to head between two players, like /h2h/D643/S0AG
# it gives the overall score and every match the two of them played against each other
@app.get("/h2h/{player1_id}/{player2_id}")
def h2h(player1_id: str, player2_id: str):
    conn = connect()
    cur = conn.cursor()
    # the api checks both players, otherwise a typo in one id would give back a fake 0:0
    for player_id in (player1_id, player2_id):
        if not player_exists(cur, player_id):
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    # this picks every match where player 1 beat player 2, or player 2 beat player 1
    # walkovers are left out through played_matches, like in the official ATP head to head
    cur.execute(
        """
        SELECT m.tourney_date, m.tourney_name, m.surface, m.round, m.winner_id, m.score
        FROM played_matches m
        WHERE (m.winner_id = %s AND m.loser_id = %s)
           OR (m.winner_id = %s AND m.loser_id = %s)
        ORDER BY m.tourney_date DESC, m.match_num DESC
        """,
        (player1_id, player2_id, player2_id, player1_id),   # the order matters here, it has to follow the four %s in the sql
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # the api counts the wins while it goes through the matches
    player1_wins = 0
    player2_wins = 0
    matches = []
    for row in rows:
        # row[4] is the winner id, and whoever won gets the point
        if row[4] == player1_id:
            player1_wins += 1   # += 1 means add one
        else:
            player2_wins += 1   # only these two can be the winner, so if it's not player 1 it's always player 2

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
