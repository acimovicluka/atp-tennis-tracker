import csv
import io
import os
import requests
import psycopg2

# TML repo - swapped in after the Sackmann repo went down.
# keep this in one place so it's easy to change again if needed
BASE_URL = "https://raw.githubusercontent.com/Tennismylife/TML-Database/master"
SEASONS = [2026]

# read from the environment so nothing real ends up in the repo.
# the defaults are just the local docker container
DB = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "dbname": os.getenv("DB_NAME", "tennis"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "tennis123"),
}


def download_season(year):
    """Download one season CSV, return rows as dicts."""
    url = f"{BASE_URL}/{year}.csv"
    print(f"Downloading {url}")
    response = requests.get(url, timeout=60)
    response.raise_for_status()  # fail loudly on 404 instead of loading nothing
    return list(csv.DictReader(io.StringIO(response.text)))


# --- helpers for cleaning CSV values ---

def to_int(value):
    """Everything in the CSV is a string and lots of fields are empty.
    Returns None instead of blowing up when the value isnt a number."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_date(value):
    """20260102 -> 2026-01-02"""
    # strip removes spaces around the value. the or ""` part is there because
    # None.strip() would crash - this way None just becomes an empty string
    value = (value or "").strip()
    if len(value) != 8:
        return None
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"


# --- turning CSV rows into rows for the db ---

def extract_players(rows):
    """Every match has a winner and a loser, and the same player shows up
    in lots of matches. Using a dict keyed on id keeps each one only once."""
    players = {}
    for row in rows:
        for side in ("winner", "loser"):
            # ATP ids look like B0BI / TE5L, not numbers
            player_id = (row.get(f"{side}_id") or "").strip()
            if not player_id:
                continue
            # order has to match the INSERT into players in main()
            players[player_id] = (
                player_id,
                row.get(f"{side}_name"),
                (row.get(f"{side}_hand") or None),
                to_int(row.get(f"{side}_ht")),
                (row.get(f"{side}_ioc") or None),
            )
    return list(players.values())


def extract_matches(rows):
    matches = []
    for row in rows:
        tourney_id = (row.get("tourney_id") or "").strip()
        match_num = to_int(row.get("match_num"))
        winner_id = (row.get("winner_id") or "").strip()
        loser_id = (row.get("loser_id") or "").strip()

        # can't store a match without its key or without both players
        # (the foreign key would reject it anyway)
        if not tourney_id or match_num is None or not winner_id or not loser_id:
            continue

        # order has to match the INSERT into matches in main()
        matches.append((
            tourney_id,
            match_num,
            row.get("tourney_name"),
            row.get("surface"),
            to_int(row.get("draw_size")),
            (row.get("tourney_level") or None),
            (row.get("indoor") or None),
            to_date(row.get("tourney_date")),
            winner_id,
            loser_id,
            to_int(row.get("winner_rank")),
            to_int(row.get("loser_rank")),
            row.get("score"),
            to_int(row.get("best_of")),
            row.get("round"),
            to_int(row.get("minutes")),
        ))
    return matches


def main():
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()

    for year in SEASONS:
        rows = download_season(year)
        print(f"  {len(rows)} match rows")

        # players first - matches has a foreign key on them
        players = extract_players(rows)
        cur.executemany(
            """
            INSERT INTO players (player_id, name, hand, height, country)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (player_id) DO NOTHING
            """,
            players,
        )
        print(f"  {len(players)} unique players processed")

        # ON CONFLICT means re-running this doesn't duplicate anything
        matches = extract_matches(rows)
        cur.executemany(
            """
            INSERT INTO matches (
                tourney_id, match_num, tourney_name, surface, draw_size,
                tourney_level, indoor, tourney_date, winner_id, loser_id,
                winner_rank, loser_rank, score, best_of, round, minutes
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (tourney_id, match_num) DO NOTHING
            """,
            matches,
        )
        print(f"  {len(matches)} matches processed")

    conn.commit()
    cur.close()
    conn.close()
    print("Done")


if __name__ == "__main__":
    main()
