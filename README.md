# ATP tennis tracker

ATP tennis tracker downloads ATP match results and stores them in a Postgres database. The data covers every season from 2022 onwards, including tournaments that are still in progress.

An API built with FastAPI reads from the database and calculates stats for each player: the last 10 matches, wins and losses by surface, and the head to head record between two players. Players can be searched by name.

The whole project runs with Docker Compose. Copy .env.example to .env, set a password and run docker compose up. The API runs on port 8000, and /docs lists all endpoints.

Match data comes from TennisMyLife (stats.tennismylife.org), shared under the MIT license.
