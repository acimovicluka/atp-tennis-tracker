-- database schema for ATP tennis tracker
-- the data comes from Tennismylife/TML-Database on github, one csv file per season
-- run this once to create the empty tables, the fetcher fills them later


-- players table, one row per player
-- the csv repeats name, hand and height on every match row
-- here every player is saved only once and the matches point to him by id
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,   -- ATP id like B0BI or TE5L, it has letters so it can't be a number
    name        TEXT NOT NULL,      -- NOT NULL means this field can never be empty
    hand        CHAR(1),            -- R or L, always exactly one letter
    height      SMALLINT,           -- height in cm, a small whole number is enough
    country     CHAR(3)             -- 3 letter country code like SRB, ESP or USA
);


-- matches table, one row per match
-- match stats like aces and break points are left out for now
-- they can be added later if some endpoint needs them
CREATE TABLE IF NOT EXISTS matches (
    tourney_id      TEXT NOT NULL,      -- tournament id like 2025-560
    match_num       INTEGER NOT NULL,   -- number of the match inside that tournament
    tourney_name    TEXT,
    surface         TEXT,               -- Hard, Clay or Grass
    draw_size       SMALLINT,           -- how many players are in the draw
    tourney_level   TEXT,               -- G is grand slam, A is ATP tour, D is Davis Cup, F is finals
    indoor          TEXT,
    tourney_date    DATE,               -- date from the csv, usually when the tournament starts

    -- REFERENCES means this player has to exist in the players table
    -- the database refuses any match with an unknown player
    -- that's why the fetcher always saves players first and matches after
    winner_id       TEXT REFERENCES players(player_id),
    loser_id        TEXT REFERENCES players(player_id),

    winner_rank     INTEGER,            -- ranking on the day of the match
    loser_rank      INTEGER,
    score           TEXT,               -- like 6-4 3-6 7-6(5)
    best_of         SMALLINT,           -- 3 or 5 sets
    round           TEXT,               -- R128, R64, R32, R16, QF, SF, F
    minutes         INTEGER,            -- how long the match lasted

    -- tourney_id alone repeats, one tournament has lots of matches
    -- match_num alone repeats too, every tournament has a match number 1
    -- but the two together are unique, so the same match can't be saved twice
    -- this is what makes it safe to run the fetcher again and again
    PRIMARY KEY (tourney_id, match_num)
);
