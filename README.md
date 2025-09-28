
HOW TO RUN LOCALLY (quick)

- python -m venv .venv && source .venv/bin/activate

- pip install -r requirements.txt

- Configure DB in settings.py (SQLite works for quick dev).

- python manage.py makemigrations && python manage.py migrate

- python manage.py runserver

- Register a user via POST /users/ (username, password, email). Team/players auto-created.

- Get tokens: POST /api/token/ with username/password to get access token.


POSTMAN

1 : Import both:

- FantasyFootball.postman_collection.json

- FantasyFootball.postman_environment.json

2: Select environment FantasyFootballLocal in Postman’s top-right environment dropdown.

3: Run the flow:

- Register/Login

- Copy refresh + access into environment (Tests tab can automate this too).

- All other requests will automatically inject {{base_url}} and {{access_token}}.

DOCKER
- git clone https://github.com/AliIrfanOzri/fantasy-football-backend cd fantasy-football-backend

- docker-compose up --build

- docker-compose exec web pytest -v

FIXTURES

- python manage.py loaddata seed_data.json


