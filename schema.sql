-- Schema for ATP-tennis-tracker
-- Source data: Tennismylife/TML-Database (CSV per season)

-- One row per player.
-- The source CSVs repeat player details (name, hand, height) on every single
-- match row. Storing them once here means a correction is made in one place
-- instead of thousands.
CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,   -- ATP IDs are alphanumeric (B0BI, TE5L), not numbers
    name        TEXT NOT NULL,
    hand        CHAR(1),            -- 'R' or 'L', always exactly one character
    height      SMALLINT,           -- in cm, SMALLINT is plenty
    country     CHAR(3)             -- IOC code, always 3 letters (SRB, ESP, USA)
);

-- One row per match.
-- Match stats (aces, double faults, break points) are deliberately left out
-- for now - they get added if and when an endpoint actually needs them.
CREATE TABLE IF NOT EXISTS matches (
    tourney_id      TEXT NOT NULL,
    match_num       INTEGER NOT NULL,
    tourney_name    TEXT,
    surface         TEXT,
    draw_size       SMALLINT,
    tourney_level   TEXT,    -- G = Grand Slam, A = ATP Tour, D = Davis Cup, F = Finals
    indoor          TEXT,
    tourney_date    DATE,

    -- Foreign keys: the database now refuses a match referencing a player
    -- that doesn't exist. Practical consequence: players must be inserted
    -- BEFORE matches, or the insert fails.
    winner_id       TEXT REFERENCES players(player_id),
    loser_id        TEXT REFERENCES players(player_id),

    winner_rank     INTEGER,    -- ranking at the time of the match
    loser_rank      INTEGER,
    score           TEXT,
    best_of         SMALLINT,   -- 3 or 5 sets
    round           TEXT,       -- R128, R64, R32, R16, QF, SF, F
    minutes         INTEGER,

    -- Composite key: neither column is unique on its own (a tournament has many matches, and match numbers repeat across tournaments), but the pair is. This is what stops the same match being inserted twice when
    -- the fetcher re-downloads a CSV it has already seen.
    PRIMARY KEY (tourney_id, match_num)
);