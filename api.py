from fastapi import FastAPI, HTTPException #HTTPE is for error message 
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


# used by the endpoints below so a wrong id gives 404 instead of an empty list
def player_exists(cur, player_id):
    cur.execute("SELECT 1 FROM players WHERE player_id = %s", (player_id,))
    return cur.fetchone() is not None


# first endpoint, just to see the server is up. no db yet
@app.get("/ping")
def ping():
    return {"status": "ok"}


# first endpoint that actually reads from the db, all above are just for the sake of test
@app.get("/players")
def list_players():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # no LIMIT for now, its only 750 players
    cur.execute("SELECT player_id, name, country FROM players ORDER BY name")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # rows come back as tuples, turn each one into a dict so the json has field names
    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players


# find players by name, so nobody has to know every atp ID
# has to stay ABOVE /players/{player_id}, otherwise "search" gets treated as an id
@app.get("/players/search")
def search_players(name: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # ILIKE ignores upper/lower case, the % on both sides means "anywhere in the name"
    cur.execute(
        "SELECT player_id, name, country FROM players WHERE name ILIKE %s ORDER BY name LIMIT 20",
        (f"%{name}%",),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    players = []
    for row in rows:
        players.append({"player_id": row[0], "name": row[1], "country": row[2]})
    return players



# one player, the id comes straight from the url
@app.get("/players/{player_id}") # {players} means that code take player_id as ingeteger based on player ATP ID
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

# wins and losses per surface, first thing that csv doesnt have
@app.get("/players/{player_id}/surface-stats")
def surface_stats(player_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")
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
        (player_id, player_id, player_id),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # one row per surface - surface, wins, losses
    stats = []
    for row in rows:
        stats.append({"surface": row[0], "wins": row[1], "losses": row[2]})
    return stats


@app.get("/players/{player_id}/form")
def form(player_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    if not player_exists(cur, player_id):
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")
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

    # one row for every match playerd (last 10 matches)
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


# head to head between two players - overall score plus every match they played
@app.get("/h2h/{player1_id}/{player2_id}")
def h2h(player1_id: str, player2_id: str):
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    # both have to exist, otherwise we'd return a fake 0:0
    for player_id in (player1_id, player2_id):
        if not player_exists(cur, player_id):
            cur.close()
            conn.close()
            raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    cur.execute(
        """
        SELECT m.tourney_date, m.tourney_name, m.surface, m.round, m.winner_id, m.score
        FROM matches m
        WHERE (m.winner_id = %s AND m.loser_id = %s)
           OR (m.winner_id = %s AND m.loser_id = %s)
        ORDER BY m.tourney_date DESC, m.match_num DESC
        """,
        (player1_id, player2_id, player2_id, player1_id),
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    player1_wins = 0
    player2_wins = 0
    matches = []
    for row in rows:
        # row[4] is winner_id, winner get +1 point
        if row[4] == player1_id:
            player1_wins += 1
        else:
            player2_wins += 1

        matches.append({
            "date": row[0],
            "tournament": row[1],
            "surface": row[2],
            "round": row[3],
            "winner_id": row[4],
            "score": row[5],
        })

    return {
        "player1_id": player1_id,
        "player2_id": player2_id,
        "player1_wins": player1_wins,
        "player2_wins": player2_wins,
        "matches": matches,
    }


