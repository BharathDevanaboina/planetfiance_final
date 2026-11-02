# 2. Local development and tests

## Option A: Docker (easiest)

Requirements: Docker Desktop.

```bash
docker compose up --build       # starts PostgreSQL + the API, runs migrations automatically
```

- API docs (try every endpoint in the browser): <http://localhost:8000/docs>
- Database: `localhost:5432`, user `college`, password `college`, database `college`
- Code changes in `app/` reload automatically.

Useful commands:

```bash
# The single-admin registration command requires a real, existing verified Firebase account.
docker compose exec api python -m app.cli --help                 # all operator commands
docker compose exec db psql -U college -d college                # SQL shell
docker compose down                                               # stop
docker compose down -v                                            # stop AND delete local data
```

## Option B: Python directly on your machine

Requirements: Python 3.12 and PostgreSQL 16. Start only the database with `docker compose up db`, or install PostgreSQL yourself.

```bash
python3.12 -m venv .venv
source .venv/bin/activate                 # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env                      # local settings (fakes for Firebase and Sheets)
# Fresh local legacy database only: alembic upgrade 0001
# Existing PlanetFiance database only: alembic upgrade 'planetfiance_existing@head'
# Do not use this local fake environment to register a production administrator.
uvicorn app.main:app --reload --port 8000
```

## Calling the API locally

With `AUTH_MODE=fake` (the default in `.env.example` and Docker), Firebase is simulated:

| What | Value to send |
|---|---|
| Admin requests | Header `Authorization: Bearer fake-admin:admin@college.com` |
| Student OTP token | Field `"firebase_id_token": "fake-phone:+919876543210"` (must match the mobile in the form) |
| App Check | Off locally (`APP_CHECK_ENABLED=false`). When on: header `X-Firebase-AppCheck: fake-app-check` |

Where the fake output goes:

- Uploaded files go to `var/storage/` and are served at `http://localhost:8000/media/...`.
- Google Sheets rows go to `var/sheets/Brochure Downloads.csv` and `var/sheets/Exam Registrations.csv`.

Example: upload an exam set and start an exam:

```bash
python -m app.cli generate-exam-template --output my-template.xlsx  # see the format
curl -X POST localhost:8000/api/v1/admin/exam \
  -H "Authorization: Bearer fake-admin:admin@college.com:mfa" \
  -F "name=Mock Test 1" -F "file=@my-200-questions.xlsx"
curl -X POST localhost:8000/api/v1/exam/start -H "Content-Type: application/json" \
  -d '{"name":"Ravi Kumar","mobile":"9876543210","firebase_id_token":"fake-phone:+919876543210"}'
```

## Real Firebase Email/Password test (separate local mode)

This optional mode uses the existing Firebase web app and Admin SDK only for a
local browser test. It uses a separate SQLite database and local storage; it
does not use Cloud SQL or production data.

1. Copy `config/local-firebase-auth-test.env.example` to
   `config/local-firebase-auth-test.env`. This ignored file must contain the
   existing Firebase web configuration and an absolute path to an existing
   local Admin SDK credential. Keep the credential file outside this repository.
2. Register the existing verified Email/Password account into the separate
   local SQLite allow-list only:

   ```powershell
   .\scripts\start-local-firebase-auth-test.ps1 -RegisterAdmin -AdminEmail person@example.com
   ```

3. Run the browser test server and open `http://127.0.0.1:8006/admin/`:

   ```powershell
   .\scripts\start-local-firebase-auth-test.ps1
   ```

The Firebase account must already exist, use the Email/Password provider, and
have a verified email. The script never creates or changes Firebase users.

## Using the real Google Sheet from your computer (optional)

1. `gcloud auth application-default login --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets`
2. Share a **test** spreadsheet with your own Google account, with the two tabs described in [Google Sheets setup](05-google-sheets-setup.md).
3. In `.env`: `SHEETS_BACKEND=google` and `SHEETS_SPREADSHEET_ID=<id>`.

## Tests

```bash
pytest                                      # all tests (in-memory SQLite, about 15 seconds)
pytest tests/modules/test_exam_flow.py -q   # one module
TEST_DATABASE_URL=postgresql+psycopg://college:college@localhost:5432/college_tests pytest  # against PostgreSQL
```

For the PostgreSQL run, create the empty `college_tests` database first:

```bash
docker compose exec db createdb -U college college_tests
```

- Tests never touch Firebase, Google Sheets or the cloud.
- Each test starts with a fresh database, seeded with the 3 courses.
- CI runs the tests on both SQLite and PostgreSQL (see [Deployment](07-deployment.md)).

Code style:

```bash
ruff check .       # lint
ruff format .      # auto-format
```

## Changing the database

1. Edit the models in `app/modules/<name>/models.py`.
2. Run `alembic revision --autogenerate -m "short description"`. This creates a file in `migrations/versions/`.
3. **Read the generated file** and fix anything odd. Autogenerate can't detect renames; it sees a drop plus an add.
4. Never use a generic Alembic `head` with these two branches. Test a fresh legacy database with explicit `0001`; test an existing PlanetFiance database only after its approved baseline, using `planetfiance_existing@head`.
5. Do not regenerate `db/schema.sql` from the PlanetFiance existing-database branch: its baseline is intentionally a no-op.
6. Commit the model change, the migration and `db/schema.sql` together.

Rules that keep deployments safe:

- **Never edit a migration that is already deployed.** Add a new one instead.
- **Make changes backwards compatible.** The old code keeps running for a few seconds after the migration runs during deployment. For example, add a column as nullable first, and fill it in a later release.
