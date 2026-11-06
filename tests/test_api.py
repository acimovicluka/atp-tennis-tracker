import api

# these tests call the real endpoints against the test database that conftest.py fills
# the numbers they expect come from tests/seed.sql, the comment at the top of that file lists them
# client is the fixture from conftest.py, pytest hands it in because the argument has the same name


def test_ping(client):
    assert client.get("/ping").json() == {"status": "ok"}


def test_ready_when_the_database_answers(client):
    assert client.get("/ready").status_code == 200


def test_ready_when_the_database_is_down(client, monkeypatch):
    # monkeypatch swaps something out for this one test only, and puts the real one back after
    # here it swaps connect() in api.py for a function that always fails, like it would when the database is down
    def broken_connect():
        raise Exception("database is down")

    monkeypatch.setattr(api, "connect", broken_connect)
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "database unavailable"}


def test_players_are_sorted_by_name(client):
    names = [player["name"] for player in client.get("/players").json()]   # takes only the names out of the json
    assert names == ["Alexander Zverev", "Carlos Alcaraz", "Jannik Sinner", "Novak Djokovic"]


def test_one_player(client):
    player = client.get("/players/S0AG").json()
    assert player["name"] == "Jannik Sinner"
    assert player["country"] == "ITA"


def test_unknown_player_gives_404(client):
    assert client.get("/players/XXXX").status_code == 404


def test_search_ignores_upper_and_lower_case(client):
    ids = [player["player_id"] for player in client.get("/players/search", params={"name": "ALCAR"}).json()]
    assert ids == ["A0E2"]


def test_search_with_serbian_letters(client):
    # the names in the data have no accents, so the api has to treat đ like dj
    for name in ("djok", "đok", "Đoković"):
        ids = [player["player_id"] for player in client.get("/players/search", params={"name": name}).json()]
        assert ids == ["D643"], name   # the name after the comma shows up in the error, so I can see which one failed


def test_surface_stats_leave_out_walkovers(client):
    stats = client.get("/players/S0AG/surface-stats").json()
    assert stats == [
        {"surface": "Clay", "wins": 4, "losses": 1},
        {"surface": "Hard", "wins": 1, "losses": 1},   # the W/O win doesn't count, otherwise this would be 2 wins
    ]


def test_form_is_newest_first_without_walkovers(client):
    form = client.get("/players/S0AG/form").json()
    assert len(form) == 7   # 8 matches in the data, minus the walkover
    assert form[0]["date"] == "2025-08-11"   # the first one in the list has to be the newest
    assert form[0]["result"] == "L"
    assert form[0]["opponent"] == "Novak Djokovic"


def test_form_for_unknown_player_gives_404(client):
    assert client.get("/players/XXXX/form").status_code == 404


def test_h2h(client):
    h2h = client.get("/h2h/S0AG/A0E2").json()
    assert h2h["player1_wins"] == 2
    assert h2h["player2_wins"] == 1
    assert len(h2h["matches"]) == 3   # the walkover is left out


def test_h2h_the_other_way_around(client):
    # the same two players in the opposite order, so the score has to flip too
    h2h = client.get("/h2h/A0E2/S0AG").json()
    assert h2h["player1_wins"] == 1
    assert h2h["player2_wins"] == 2


def test_h2h_with_unknown_player_gives_404(client):
    assert client.get("/h2h/S0AG/XXXX").status_code == 404


def test_metrics(client):
    # the earlier tests already sent requests, so /metrics should already be counting them
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
