import csv        # reads csv files
import io         # only used for StringIO, see download_csv
import os         # only used to find schema.sql next to this file
import requests   # downloads files from the internet

from db import connect   # opens a database connection, the settings live in db.py


# where the csv files live, one file per season (2025.csv and so on)
# TML moved from github to its own site, the github copy stopped in january 2026
# kept in one place so it's easy to swap again if the source moves one more time
BASE_URL = "https://stats.tennismylife.org/data"

# which seasons get downloaded
SEASONS = [2022, 2023, 2024, 2025, 2026]

# every file the fetcher reads: the tournament that is being played right now, plus one file per season
# finished tournaments are in the season file, the one in progress is only in ongoing_tourneys.csv
# the ongoing file goes first: on the day a tournament moves into the season file it can be in both,
# and the file that comes later wins (see main), so the finished version from the season file is the one that stays
FILES = ["ongoing_tourneys.csv"] + [f"{year}.csv" for year in SEASONS]   # makes 2022.csv, 2023.csv... out of SEASONS

# schema.sql sits next to this file, on my computer and inside the docker image
SCHEMA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")


# downloads one csv file from TML and gives back its rows
# every row comes back as a dict, so you can write row["surface"] instead of row[2]
def download_csv(name):
    url = f"{BASE_URL}/{name}"   # {name} gets replaced, so this ends with /2025.csv or /ongoing_tourneys.csv
    print(f"Downloading {url}")
    response = requests.get(url, timeout=60)   # gives up after a minute instead of hanging forever
    response.raise_for_status()   # if the site returns an error like 404, stop right here instead of loading nothing
    # read this line from the inside out:
    # response.text is the whole file as one long piece of text
    # StringIO makes that text act like a file, because the csv reader expects a file
    # DictReader turns every line into a dict, using the first line as column names
    # list() collects all of them into one list
    return list(csv.DictReader(io.StringIO(response.text)))


# helpers for cleaning csv values
# everything in a csv is text and lots of fields are empty,
# so these turn the text into proper values, or None when there's nothing usable


# turns text into a whole number, so "170" becomes 170
# empty or broken values become None instead of crashing the whole run
def to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):   # TypeError when the value is None, ValueError when it's text like "" or "abc"
        return None


# turns the csv date 20250824 into 2025-08-24, the format postgres understands
def to_date(value):
    value = (value or "").strip()   # None becomes "" so strip() can't crash, strip() removes spaces at both ends
    if len(value) != 8:   # anything that isn't exactly 8 characters isn't a date we can read
        return None
    return f"{value[0:4]}-{value[4:6]}-{value[6:8]}"   # cut into year, month and day. [0:4] means characters 0 to 3


# turning csv rows into rows for the database


# collects every player from the matches, each player only once
# the same player shows up in lots of matches, so they go into a dict keyed on the player id
# a dict can't have the same key twice, so duplicates just disappear
def extract_players(rows):
    players = {}
    for row in rows:
        for side in ("winner", "loser"):   # every match has two players, this goes through both of them
            player_id = (row.get(f"{side}_id") or "").strip()   # winner_id on the first pass, loser_id on the second
            if not player_id:
                continue   # no id, skip this one and move on to the next
            # the order here has to match the INSERT into players in main()
            players[player_id] = (
                player_id,
                row.get(f"{side}_name"),
                (row.get(f"{side}_hand") or None),   # empty text becomes None, which ends up as NULL in the database
                to_int(row.get(f"{side}_ht")),
                (row.get(f"{side}_ioc") or None),
            )
    return list(players.values())   # only the values, the ids are already inside them


# turns csv rows into rows for the matches table
# rows that are missing the tournament or one of the players get skipped
def extract_matches(rows):
    matches = []

    # some 2025 tournaments (US Open, Cincinnati, Shanghai and a few more) have no match number in the csv
    # without it a match can't be saved, so we number those ourselves: 1, 2, 3 and so on per tournament
    # the same csv always gives the same numbers, so running the fetcher again still doesn't create duplicates
    generated_num = {}   # remembers the last number given out for each tournament

    # the source sometimes has the same match twice under two match numbers (Gijon 2022, a Davis Cup tie in 2024)
    # two players can only meet once in the same round of the same tournament, so the second copy gets skipped
    seen = set()   # a set is like a list that can't hold the same thing twice, and checking "is it in there" is fast

    for row in rows:
        tourney_id = (row.get("tourney_id") or "").strip()
        match_num = to_int(row.get("match_num"))
        winner_id = (row.get("winner_id") or "").strip()
        loser_id = (row.get("loser_id") or "").strip()

        # can't save a match without a tournament or without both players
        # the database would refuse it anyway because of the foreign key
        if not tourney_id or not winner_id or not loser_id:
            continue

        same_match = (tourney_id, row.get("round"), winner_id, loser_id)
        if same_match in seen:
            continue
        seen.add(same_match)

        if match_num is None:
            generated_num[tourney_id] = generated_num.get(tourney_id, 0) + 1   # .get(..., 0) gives 0 if this tournament has no number yet
            match_num = generated_num[tourney_id]

        # the order here has to match the INSERT into matches in main()
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


# the actual run, step by step:
# connect to the database, make sure the schema is up to date, go through every file,
# save players first and matches after, and commit only at the very end
def main():
    conn = connect()   # this is where python really connects
    cur = conn.cursor()   # the cursor is what sends sql through the connection

    # run schema.sql again, so anything new in it (a table, a view) also lands in a database that already exists
    # postgres only runs it by itself on the very first start, see the top of schema.sql
    with open(SCHEMA_FILE, encoding="utf-8") as f:   # with closes the file by itself when the block ends
        cur.execute(f.read())

    for name in FILES:
        rows = download_csv(name)
        print(f"  {len(rows)} match rows")

        # players go in first, because matches point to them (foreign key)
        # executemany runs the same INSERT once for every player in the list
        # %s are placeholders, psycopg2 fills them in safely. never glue values into sql by hand
        # ON CONFLICT DO NOTHING skips players that are already in the table
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

        # the source fixes and renumbers matches after a tournament is over,
        # and a tournament in progress gets numbered differently once it moves into the season file
        # if we only added new rows, the old version would stay next to the fixed one and count twice
        # so every tournament in this file is first removed and then saved again exactly as the csv has it now
        # this is safe because nothing is saved until the commit at the end, if anything fails the old data stays
        matches = extract_matches(rows)
        tourney_ids = list({match[0] for match in matches})   # match[0] is the tourney_id, the {} removes repeats
        cur.execute("DELETE FROM matches WHERE tourney_id = ANY(%s)", (tourney_ids,))   # ANY means "is one of these"
        print(f"  {cur.rowcount} old matches removed from {len(tourney_ids)} tournaments")

        # ON CONFLICT is still here as a safety net, for the rare csv that has two matches with the same number
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

    # commit is what saves everything for real
    # until this line nothing is permanent, so if the script crashes halfway the database stays untouched
    conn.commit()
    cur.close()
    conn.close()
    print("Done")


# only run main() when the file is started directly with python fetcher.py
# without these two lines python would just read the functions and stop without doing anything
if __name__ == "__main__":
    main()
