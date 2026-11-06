-- this file describes what the database looks like: which tables there are and which columns they have
-- it holds no data itself, the fetcher fills the tables later
-- the data comes from TennisMyLife (stats.tennismylife.org), one csv file per season
--
-- this file runs in two places:
-- postgres runs it by itself the very first time the database starts (when it's still empty),
-- and the fetcher runs it again at the start of every run
-- that way, when I add something new here (a table, a view), it also reaches a database that already exists
-- so everything in this file has to be safe to run again and again (idempotent),
-- that's what IF NOT EXISTS and OR REPLACE are for
-- this only covers adding new things: if I change a column that already exists,
-- CREATE TABLE IF NOT EXISTS sees the table is there and does nothing, so I'd need an ALTER TABLE by hand


-- unaccent is a postgres extension that removes accents from text, so the api can find "Djokovic" when you search for "đok"
-- it comes with postgres, but it's off until you switch it on, and this line switches it on
CREATE EXTENSION IF NOT EXISTS unaccent;


-- the players table, one row for every player
-- the csv repeats the name, hand and height of both players on every single match row
-- here every player is saved only once, and the matches point to him by his id (normalization)
-- inside CREATE TABLE every line is one column: its name, its type and its rules
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,   -- ATP id like D643 or S0AG, it has letters in it so the column is TEXT and not a number
                                    -- PRIMARY KEY means no two players can have the same id and it can never be empty
    name        TEXT NOT NULL,      -- NOT NULL means postgres refuses a player without a name
    hand        CHAR(1),            -- R or L, CHAR(1) means always exactly one letter
    height      SMALLINT,           -- height in cm, a small whole number is enough and takes less space than INTEGER
    country     CHAR(3)             -- 3 letter country code like SRB, ESP or USA
);


-- the matches table, one row for every match
-- I left out match stats like aces and break points for now
-- I can add them later if some endpoint needs them
CREATE TABLE IF NOT EXISTS matches (
    tourney_id      TEXT NOT NULL,      -- tournament id like 2025-560
    match_num       INTEGER NOT NULL,   -- number of the match inside that tournament
    tourney_name    TEXT,
    surface         TEXT,               -- Hard, Clay or Grass
    draw_size       SMALLINT,           -- how many players are in the draw
    tourney_level   TEXT,               -- G is grand slam, A is ATP tour, D is Davis Cup, F is finals
    indoor          TEXT,
    tourney_date    DATE,               -- the date from the csv, usually the day the tournament starts

    -- REFERENCES players(player_id) is a foreign key: postgres only accepts an id here
    -- if that id already exists in the player_id column of the players table
    -- a match only keeps the player's id, not his name, and the api gets the name from players with a JOIN
    -- if the fetcher tries to save a match with an unknown player (for example winner_id 'X999'), postgres refuses it
    -- that's why the fetcher always saves the players first and the matches after
    -- there are two because every match has two players, and both point to the same players table
    winner_id       TEXT REFERENCES players(player_id),
    loser_id        TEXT REFERENCES players(player_id),

    winner_rank     INTEGER,            -- ranking on the day of the match
    loser_rank      INTEGER,
    score           TEXT,               -- like 6-4 3-6 7-6(5)
    best_of         SMALLINT,           -- 3 or 5 sets
    round           TEXT,               -- R128, R64, R32, R16, QF, SF, F
    minutes         INTEGER,            -- how long the match lasted

    -- this is a composite primary key, made out of two columns together
    -- tourney_id alone repeats, because one tournament has lots of matches
    -- match_num alone repeats too, because every tournament has a match number 1
    -- but the two together are unique, so postgres never lets the same match in twice
    -- the fetcher's ON CONFLICT relies on this, and it's what makes it safe to run the fetcher again and again
    PRIMARY KEY (tourney_id, match_num)
);


-- played_matches is a view with every match that was actually played, so everything except walkovers
-- a walkover (score W/O) means one player didn't show up, so no tennis was played at all
-- official ATP stats leave walkovers out of win/loss records and head to head, so this view does the same
-- retirements (RET) and defaults (DEF) stay in, because ATP counts those as normal wins and losses
-- a view is a saved SELECT that you can use like a table, but it doesn't store any data itself:
-- every time the api asks for played_matches, postgres runs this SELECT on the matches table
-- the api and grafana read from this view, and the matches table still keeps everything exactly like the csv has it
-- score IS NULL is there because without it postgres would also drop matches that have no score at all
-- (in sql, NULL NOT LIKE something is neither true nor false, so the row would get thrown out)
CREATE OR REPLACE VIEW played_matches AS
SELECT *
FROM matches
WHERE score IS NULL OR score NOT LIKE '%W/O%';
