# fetcher.py downloads the match results, cleans them up and saves them into the database
# it doesn't stay running like the api, it does its job and stops
# on kubernetes it gets started every morning at 6, with compose it runs once when everything starts

import csv        # python's own tool for reading csv files
import io         # only needed for StringIO, explained in download_csv
import os         # only needed to find schema.sql
import requests   # downloads files from the internet, it's in requirements.txt

from db import connect   # the function from db.py that opens the database connection


# this is where all the csv files are, one file for each season (2022.csv and so on)
# the source already moved twice (first Sackmann's repo, then the TML github copy that stopped in january 2026)
# so the address is written only here, and if it moves again I only change this one line
BASE_URL = "https://stats.tennismylife.org/data"

# the seasons I want in the database (2022 is the earlies in TML base)
SEASONS = [2022, 2023, 2024, 2025, 2026]

# the list of files the fetcher goes through, in this order
# the line at the end takes every year from SEASONS and adds .csv, so it gives 2022.csv, 2023.csv...
# ongoing_tourneys.csv has the tournament that's being played right now, finished ones are in the season files
# it goes first on purpose: on the day a tournament ends it can be in both files,
# and since every file replaces its tournaments (see main), the season file comes later and its finished version stays
FILES = ["ongoing_tourneys.csv"] + [f"{year}.csv" for year in SEASONS]

# the full path to schema.sql, which sits in the same folder as this file
# read it from the inside out: __file__ is this file, dirname is its folder, join adds schema.sql to it
# this way it works both on my computer and inside the docker image (/app/schema.sql)
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


# downloads one csv file and gives back all of its rows
# every row comes back as a dict, so later I can write row["surface"] instead of guessing it's row[2]
def download_csv(name):
    url = f"{BASE_URL}/{name}"   # glues the address and the file name together, like .../data/2025.csv
    print(f"Downloading {url}")
    response = requests.get(url, timeout=60)   # if the site doesn't answer in a minute, give up instead of waiting forever
    response.raise_for_status()   # if the site sends back an error (like 404), stop here, otherwise we'd go on with nothing
    # this line does a few things at once, read it from the inside out:
    # response.text is the whole file as one big piece of text
    # StringIO lets that text pretend it's a file, because the csv reader only knows how to read files
    # DictReader reads it line by line and uses the first line (the header) as the names of the columns
    # list() puts all the rows together into one list
    return list(csv.DictReader(io.StringIO(response.text)))


# the next two functions clean up values from the csv
# everything in a csv is just text, and a lot of fields are empty
# the database wants real numbers and dates, so these turn the text into the right type,
# and if there's nothing usable they give back None, which ends up as an empty (NULL) field in the database


# turns text into a whole number, so "188" becomes 188
# try means: give it a go, and if it fails, do what's under except instead of crashing
# without this, one empty height field would stop the whole fetcher
def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):   # TypeError when there's no value at all (None), ValueError for text like "" or "abc"
        return None


# the csv writes dates as 20250824, postgres wants 2025-08-24, so this adds the dashes
def to_date(value):
    value = (value or "").strip()   # if there's no value use "" so strip() doesn't crash, strip() cuts spaces off both ends
    if len(value) != 8:   # a real date here is always exactly 8 characters, anything else gets skipped
        return None
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"   # [0:4] takes characters 0 to 3 (the year), then the month, then the day


# the next two functions turn the csv rows into rows that fit the database tables


# every csv row is one match, and every match has two players in it
# the same player shows up in hundreds of matches, but in the players table he should be there only once
# so they go into a dict where the player id is the key
# a dict can't have the same key twice, so when Sinner shows up again he just overwrites himself
def extract_players(rows):
    players = {}
    for row in rows:
        for side in ("winner", "loser"):   # first round reads the winner, second round the loser of the same match
            player_id = (row.get(f"{side}_id") or "").strip()   # becomes winner_id the first time and loser_id the second time
            if not player_id:
                continue   # no id means I can't save this player, so skip him and go on
            # the order of these values has to be the same as the columns in the INSERT into players in main()
            players[player_id] = (
                player_id,
                row.get(f"{side}_name"),
                (row.get(f"{side}_hand") or None),   # an empty field becomes None, so the database gets NULL and not ""
                to_int(row.get(f"{side}_ht")),
                (row.get(f"{side}_ioc") or None),
            )
    return list(players.values())   # I only need the values, the id is already the first thing in each of them


# turns the csv rows into rows for the matches table
# it also deals with the messy parts of the source, explained below
def extract_matches(rows):
    matches = []

    # some 2025 tournaments (US Open, Cincinnati, Shanghai and a few more) have no match number in the csv
    # a match can't be saved without one, because the number is part of the primary key
    # so the fetcher numbers those itself: 1, 2, 3 and so on, separately for every tournament
    # the csv always comes in the same order, so the numbers are always the same and running it again makes no duplicates
    generated_num = {}   # remembers which number each tournament got up to

    # sometimes the source has the same match twice, just with two different match numbers (Gijon 2022, a Davis Cup tie in 2024)
    # two players can't play each other twice in the same round of the same tournament,
    # so tournament + round + winner + loser is enough to recognize a copy, and the copy gets skipped
    seen = set()   # a set is like a list that can't hold the same thing twice, and checking if something is in it is fast

    for row in rows:
        tourney_id = (row.get("tourney_id") or "").strip()
        match_num = to_int(row.get("match_num"))
        winner_id = (row.get("winner_id") or "").strip()
        loser_id = (row.get("loser_id") or "").strip()

        # a match without a tournament or without both players is useless,
        # and the database would refuse it anyway because of the foreign key, so skip it
        if not tourney_id or not winner_id or not loser_id:
            continue

        # if I've already seen this exact match in this file, it's a copy, skip it
        same_match = (tourney_id, row.get("round"), winner_id, loser_id)
        if same_match in seen:
            continue
        seen.add(same_match)

        # no match number in the csv, so give it the next free number for this tournament
        if match_num is None:
            generated_num[tourney_id] = generated_num.get(tourney_id, 0) + 1   # .get(..., 0) starts from 0 the first time
            match_num = generated_num[tourney_id]

        # one row for the database
        # the order of these values has to be the same as the columns in the INSERT into matches in main()
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


# this is where the actual work happens, everything above is just helpers
# in short: connect to the database, update the schema, go through every file,
# save the players first and the matches after, and only at the very end save everything for real with commit
def main():
    conn = connect()   # opens the connection to the database, the settings come from db.py
    cur = conn.cursor()   # the cursor is what I use to send sql through that connection

    # run schema.sql every time, so if I add something new to it (a table, a view)
    # it also gets into a database that already exists
    # postgres runs it by itself only the very first time, when the database is empty
    with open(SCHEMA_FILE, encoding="utf-8") as f:   # with closes the file by itself when it's done, even if something breaks
        cur.execute(f.read())

    for name in FILES:
        rows = download_csv(name)
        print(f"  {len(rows)} match rows")

        # players have to go in before the matches, because a match points to its players (foreign key)
        # executemany runs the same INSERT once for every player in the list
        # the %s marks are empty spots that psycopg2 fills in safely with the real values
        # I never glue values straight into the sql text, because that's how sql injection happens
        # ON CONFLICT DO NOTHING means: if this player is already in the table, just skip him, no error
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

        # with matches it's not enough to only add the new ones
        # the source fixes and renumbers matches after a tournament ends,
        # and a tournament that's still going is numbered differently than in the season file later
        # if I only added new rows, the old version would stay next to the fixed one and the match would count twice
        # so every tournament in this file first gets deleted, and then saved again exactly like the csv has it today
        # this is safe because nothing is really saved until the commit at the end, if it breaks the old data stays
        matches = extract_matches(rows)
        tourney_ids = list({match[0] for match in matches})   # match[0] is the tourney_id, the {} keeps each tournament only once
        cur.execute("DELETE FROM matches WHERE tourney_id = ANY(%s)", (tourney_ids,))   # ANY means "the tourney_id is one of these"
        print(f"  {cur.rowcount} old matches removed from {len(tourney_ids)} tournaments")

        # ON CONFLICT is still here just in case, for a csv that has two matches with the same number
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

    # commit is the moment everything gets saved for real
    # everything before this line is one transaction: if the fetcher crashes halfway (say the internet drops),
    # postgres throws away all the changes and the database stays exactly like it was before the run
    # the api keeps showing the old data the whole time, until the new data is complete
    conn.commit()
    cur.close()
    conn.close()
    print("Done")


# main() only runs when I start this file myself with python fetcher.py
# when another file does import fetcher (like the tests do), python only reads the functions and nothing runs,
# that's why the tests can check to_int or extract_matches without downloading anything or touching the database
if __name__ == "__main__":
    main()
