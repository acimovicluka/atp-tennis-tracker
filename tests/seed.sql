-- small made up data for the tests, loaded into an empty test database
-- the real data changes every day, so the tests can't know the right answers for it
-- here we know exactly what is inside, so we also know exactly what the api has to return
--
-- what the tests expect from this data, for Sinner (S0AG):
--   clay: 4 wins, 1 loss    hard: 1 win, 1 loss (the walkover in the last tournament doesn't count)
--   7 played matches, the newest one is the final he lost to Djokovic
--   head to head with Alcaraz: Sinner 2, Alcaraz 1 (again without the walkover)


INSERT INTO players (player_id, name, hand, height, country) VALUES
    ('D643', 'Novak Djokovic',   'R', 188, 'SRB'),
    ('S0AG', 'Jannik Sinner',    'R', 191, 'ITA'),
    ('A0E2', 'Carlos Alcaraz',   'R', 183, 'ESP'),
    ('Z355', 'Alexander Zverev', 'R', 198, 'GER');


INSERT INTO matches (tourney_id, match_num, tourney_name, surface, tourney_date, winner_id, loser_id, score, round) VALUES
    -- first clay tournament, Sinner wins both
    ('2025-100', 1, 'Clay Test Open',    'Clay', '2025-04-07', 'S0AG', 'Z355', '6-3 6-4',       'R16'),
    ('2025-100', 2, 'Clay Test Open',    'Clay', '2025-04-07', 'A0E2', 'D643', '6-4 7-5',       'R16'),
    ('2025-100', 3, 'Clay Test Open',    'Clay', '2025-04-07', 'S0AG', 'A0E2', '6-2 6-3',       'SF'),

    -- second clay tournament, Sinner wins two and loses the final to Alcaraz
    ('2025-200', 1, 'Clay Test Masters', 'Clay', '2025-05-05', 'S0AG', 'D643', '7-6(4) 6-4',    'QF'),
    ('2025-200', 2, 'Clay Test Masters', 'Clay', '2025-05-05', 'S0AG', 'Z355', '6-1 6-1',       'SF'),
    ('2025-200', 3, 'Clay Test Masters', 'Clay', '2025-05-05', 'A0E2', 'S0AG', '6-4 3-6 6-3',   'F'),

    -- hard court, Alcaraz retires (RET counts as a normal win), then Sinner loses the final to Djokovic
    ('2025-300', 1, 'Hard Test Cup',     'Hard', '2025-08-11', 'S0AG', 'A0E2', '6-3 2-1 RET',   'SF'),
    ('2025-300', 2, 'Hard Test Cup',     'Hard', '2025-08-11', 'D643', 'S0AG', '6-4 6-4',       'F'),

    -- a walkover, no tennis was played, so the stats have to leave it out
    ('2025-400', 1, 'Indoor Test Open',  'Hard', '2025-10-27', 'S0AG', 'A0E2', 'W/O',           'F');
