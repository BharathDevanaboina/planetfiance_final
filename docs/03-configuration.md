# 3. Configuration

All settings are **environment variables**. The application reads them at start-up and refuses to start in staging or production if something unsafe or missing is detected. Check any time with `python -m app.cli check-config`.

## Where settings live

| Environment | Non-secret settings | Secrets |
|---|---|---|
| Local (Docker) | `docker-compose.yml` (`environment:`) | none (fakes) |
| Local (Python) | `.env` (copy of `.env.example`) | none (fakes) |
| Staging | `config/staging.env.yaml` | Google Secret Manager, listed in `SECRETS` in `config/staging.deploy.env` |
| Production | `config/production.env.yaml` | Google Secret Manager, listed in `SECRETS` in `config/production.deploy.env` |

**To change a setting in the cloud:** edit the YAML file, commit, and deploy ([Deployment](07-deployment.md)). The deploy script replaces all variables on the service with the file's contents, so the file is always the source of truth. Never change variables by hand in the Cloud Console; the next deploy would undo it.

Before the first deploy, replace every `REPLACE_ME` value. The deploy script refuses to run while any remain.

## All settings

### General

| Variable | Default | Meaning |
|---|---|---|
| `APP_ENV` | `local` | `local`, `test`, `staging` or `production`. Staging and production turn on strict checks |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `ENABLED_MODULES` | `all` | `all`, or a comma list of modules to run in this service ([Architecture](01-architecture.md#splitting-a-module-into-its-own-service-later)) |
| `CORS_ALLOWED_ORIGINS` | empty | Comma list of websites allowed to call the API directly from a browser, e.g. `https://college.com,https://www.college.com`. Not needed for calls through the Firebase Hosting `/api` rewrite, but harmless; set it to your site's domain |

### Database

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | empty | Full SQLAlchemy URL; overrides all the above (handy for local work) |
| `DB_POOL_SIZE` | `5` | Connections per container |
| `DB_MAX_OVERFLOW` | `5` | Extra connections per container. Max connections = containers × (pool + overflow); keep it below the Cloud SQL limit |
| `DB_USER` | `college` | Database user and name |
| `DB_NAME` | `college` | Database name |
| `DB_PASSWORD` | empty | Secret (`college-db-password`) |
| `DB_HOST` | `localhost` | Used when not on Cloud SQL |
| `DB_PORT` | `5432` | Used when not on Cloud SQL |
| `CLOUD_SQL_CONNECTION_NAME` | empty | `PROJECT:REGION:INSTANCE`. When set, the app connects through the Cloud SQL socket (Cloud Run) |

### Firebase Auth and App Check

| Variable | Default | Meaning |
|---|---|---|
| `GCP_PROJECT_ID` | empty | The Firebase/Google Cloud project ID |
| `AUTH_MODE` | `firebase` | `fake` only for local and tests |
| `APP_CHECK_ENABLED` | `true` | Public form submissions must carry a valid App Check token |
| `OTP_MAX_AGE_SECONDS` | `600` | The phone OTP must have been completed within this many seconds |
| `DELETE_FIREBASE_PHONE_USER` | `true` | Remove the temporary Firebase phone user after the details reach Google Sheets |

### File storage

| Variable | Default | Meaning |
|---|---|---|
| `STORAGE_BACKEND` | `firebase` | `local` only for local work |
| `STORAGE_BUCKET` | empty | e.g. `college-prod.firebasestorage.app` |
| `LOCAL_STORAGE_DIR` | `var/storage` | Local only |
| `PUBLIC_BASE_URL` | `http://localhost:8000` | Local only |
| `MAX_IMAGE_UPLOAD_MB` | `10` | Upload limit |
| `MAX_PDF_UPLOAD_MB` | `25` | Upload limit |
| `MAX_EXCEL_UPLOAD_MB` | `5` | Upload limit. Cloud Run's request limit is 32 MB |

### Google Sheets

| Variable | Default | Meaning |
|---|---|---|
| `SHEETS_BACKEND` | `google` | `fake` writes CSV files (local only) |
| `SHEETS_SPREADSHEET_ID` | empty | The long ID in the sheet's URL: `docs.google.com/spreadsheets/d/<ID>/edit` |
| `SHEETS_TAB_BROCHURE` | `Brochure Downloads` | Tab name (must match exactly) |
| `SHEETS_TAB_EXAM` | `Exam Registrations` | Tab name (must match exactly) |
| `SHEETS_TIMEOUT_SECONDS` | `8` | After this the row goes to the retry queue |

### Scheduled retry endpoint (`/internal/lead-sync/flush`)

| Variable | Default | Meaning |
|---|---|---|
| `INTERNAL_AUTH_MODE` | `oidc` | `oidc`: Cloud Scheduler signs each call with a Google identity token; `token`: shared secret header (local) |
| `INTERNAL_OIDC_AUDIENCE` | empty | The Cloud Run service URL |
| `INTERNAL_ALLOWED_SERVICE_ACCOUNTS` | empty | Comma list of service accounts allowed to call it (the scheduler account) |
| `INTERNAL_TASK_TOKEN` | empty | Only for `token` mode |

### Exam

| Variable | Default | Meaning |
|---|---|---|
| `EXAM_TOKEN_SECRET` | dev value locally | **Secret** (`college-exam-token-secret`), at least 32 characters. Signs exam attempt tokens. Changing it invalidates exams in progress |
| `EXAM_DURATION_MINUTES` | `150` | Exam length |
| `EXAM_SUBMIT_GRACE_SECONDS` | `300` | Extra time allowed for the final submit to arrive (slow networks) |
| `RATE_LIMIT_ENABLED` | `true` | Per-container limits on public endpoints |

## Deployment settings (`config/<env>.deploy.env`)

Read only by `scripts/deploy.sh` and `scripts/run-cli.sh`:

| Variable | Meaning |
|---|---|
| `PROJECT_ID`, `REGION` | Google Cloud project and region (`asia-south1` = Mumbai) |
| `SERVICE_NAME` | Cloud Run service name (`college-api`) |
| `MIGRATE_JOB_NAME` | Cloud Run job that runs the explicit `planetfiance_existing@head` target before each existing-database deploy |
| `ARTIFACT_REPOSITORY`, `IMAGE_NAME` | Where container images are stored |
| `RUNTIME_SERVICE_ACCOUNT` | Identity the service runs as (`college-api@...`) |
| `CLOUD_SQL_INSTANCE` | `PROJECT:REGION:INSTANCE` |
| `MIN_INSTANCES`, `MAX_INSTANCES` | Containers kept warm / maximum. Production keeps 1 warm, so there are no cold starts |
| `CPU`, `MEMORY`, `CONCURRENCY`, `REQUEST_TIMEOUT` | Container size, requests per container, seconds per request |
| `SECRETS` | `VARIABLE=secret-name:version` pairs mounted from Secret Manager |

## Secrets

| Secret Manager name | Becomes variable | How to create |
|---|---|---|
| `college-db-password` | `DB_PASSWORD` | [Google Cloud setup](06-google-cloud-setup.md), step 5 |
| `college-exam-token-secret` | `EXAM_TOKEN_SECRET` | Same step |

Secrets are never stored in Git, in the container image or in GitHub.
