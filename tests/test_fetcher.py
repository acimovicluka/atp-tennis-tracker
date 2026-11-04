from fetcher import extract_matches, extract_players, to_date, to_int

# these only test the cleaning functions, so they don't need a database at all
# every test is a plain function whose name starts with test_, pytest finds them by that name
# assert means "this has to be true", if it isn't the test fails and pytest shows both values


def test_to_int_turns_text_into_a_number():
    assert to_int("170") == 170


def test_to_int_gives_none_for_empty_or_broken_values():
    assert to_int("") is None
    assert to_int(None) is None
    assert to_int("abc") is None


def test_to_date_adds_the_dashes():
    assert to_date("20250824") == "2025-08-24"


def test_to_date_gives_none_for_anything_that_is_not_a_date():
    assert to_date("") is None
    assert to_date(None) is None
    assert to_date("2025") is None


# the smallest csv row the extract functions can work with, the rest of the columns can stay empty
def row(tourney_id="2025-1", match_num="1", winner_id="A", loser_id="B", round="R32"):
    return {
        "tourney_id": tourney_id,
        "match_num": match_num,
        "winner_id": winner_id,
        "winner_name": f"Player {winner_id}",
        "loser_id": loser_id,
        "loser_name": f"Player {loser_id}",
        "round": round,
    }


def test_extract_players_keeps_every_player_once():
    # player A shows up in both matches, but has to come out only once
    players = extract_players([row(winner_id="A", loser_id="B"), row(match_num="2", winner_id="A", loser_id="C")])
    assert sorted(player[0] for player in players) == ["A", "B", "C"]


def test_extract_matches_skips_rows_without_both_players():
    assert extract_matches([row(loser_id="")]) == []


def test_extract_matches_numbers_matches_that_have_no_number():
    # like the US Open 2025 rows in the real csv
    matches = extract_matches([
        row(match_num="", winner_id="A", loser_id="B"),
        row(match_num="", winner_id="C", loser_id="D"),
    ])
    assert [match[1] for match in matches] == [1, 2]   # match[1] is match_num


def test_extract_matches_skips_the_same_match_listed_twice():
    # same tournament, round and players under two numbers, like Gijon 2022 in the real csv
    matches = extract_matches([row(match_num="5"), row(match_num="6")])
    assert len(matches) == 1
