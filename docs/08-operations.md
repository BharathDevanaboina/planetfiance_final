# 8. Operations and maintenance

All commands assume `gcloud config set project college-prod` (or staging) and `REGION=asia-south1`.

## Common admin tasks

| Task | How |
|---|---|
| Initialize the sole admin | Once only: `./scripts/run-cli.sh production grant-existing-admin --email existing-verified@example.com --name "Name"`. The command refuses if an `admin_users` record already exists and never creates or changes a Firebase user. |
| List admins | `./scripts/run-cli.sh production list-admins` (output in job logs) |
| Admin password | Managed directly in Firebase Authentication; the application intentionally exposes no public reset flow. |
| Replace an exam set | Admin portal → Exam sets → **Validate** the new file → **Delete** the old set → **Upload** into the empty slot. Students who started on the old set must start again |
| Check an exam file offline | `python -m app.cli validate-exam-file my-set.xlsx` |
| Get the Excel template | Admin portal, or `python -m app.cli generate-exam-template` |
| Replace a brochure | Admin portal → Brochures → upload the new PDF for that course (the old file is deleted) |
| Exam registration cannot reach Google Sheets | The exam start is refused and the student can retry. A retry queue is unavailable until `pending_sheet_rows` is separately implemented. |

## Backups

### What is backed up automatically

| Data | Backup | Kept |
|---|---|---|
| Database (all admin-managed content and exam sets) | Cloud SQL daily backup (02:00 IST) + point-in-time recovery (any second in the last 7 days) | 14 daily backups |
| Images and brochure PDFs | Cloud Storage versioning + 30-day soft delete | 30 days after change or delete |
| Student submissions | Google Sheets version history | Google-managed |
| Code and configuration | Git (GitHub) | Forever |
| Container images | Artifact Registry | Until deleted |

### Manual backup before risky changes

```bash
gcloud sql backups create --instance=college-db --description="before change"
gcloud sql backups list --instance=college-db
```

### Monthly export to a file (recommended)

An export is a plain SQL file you can keep outside Cloud SQL:

```bash
gcloud storage buckets create gs://college-prod-db-exports --location=asia-south1 --uniform-bucket-level-access
SQL_SA=$(gcloud sql instances describe college-db --format='value(serviceAccountEmailAddress)')
gcloud storage buckets add-iam-policy-binding gs://college-prod-db-exports --member="serviceAccount:$SQL_SA" --role=roles/storage.objectAdmin
gcloud sql export sql college-db gs://college-prod-db-exports/college-$(date +%Y-%m-%d).sql --database=college
```

To make it automatic, create a Cloud Scheduler job that calls the Cloud SQL Admin API `export` method monthly, or put a calendar reminder for the admin.

## Restore

### A. Undo a mistake from the last 7 days (safest: restore into a NEW instance, then switch)

1. Pick a time just before the mistake, in UTC. Then clone at that time:

   ```bash
   gcloud sql instances clone college-db college-db-restored --point-in-time="2026-10-30T08:00:00Z"
   ```

2. Check the data. Connect with Cloud SQL Studio in the console, or:

   ```bash
   gcloud sql connect college-db-restored --user=college_app --database=college
   ```

3. Switch the app over:
   - Change `CLOUD_SQL_INSTANCE` in `config/production.deploy.env` and `CLOUD_SQL_CONNECTION_NAME` in `config/production.env.yaml` to `college-prod:asia-south1:college-db-restored`.
   - Deploy.
   - Re-create the backup settings on the new instance (`gcloud sql instances patch ... --backup-start-time ... --enable-point-in-time-recovery`).

4. Delete the old instance only after a few days, when you are sure.

### B. Restore a daily backup over the existing instance (overwrites everything in it)

```bash
gcloud sql backups list --instance=college-db
gcloud sql backups restore <BACKUP_ID> --restore-instance=college-db
```

### C. Restore a deleted or overwritten file in Storage

```bash
gcloud storage ls --all-versions gs://college-prod.firebasestorage.app/private/brochures/PGDM/
gcloud storage objects list --soft-deleted gs://college-prod.firebasestorage.app/app/banners/
gcloud storage restore gs://college-prod.firebasestorage.app/<path>#<generation>
```

Usually it's faster to simply upload the image or brochure again in the admin portal.

**Practise a restore every 3 months on staging** so it's familiar when it matters.

### Google Sheets

- Version history: **File → Version history → See version history** → pick a version → **Restore**.
- Monthly: **File → Download → Microsoft Excel** and store the file in the college's Google Drive or on a computer.

## Rotating secrets

| Secret | How | Effect |
|---|---|---|
| Database password | `openssl rand -base64 32 \| tr -dc 'A-Za-z0-9' \| head -c 32`; then `gcloud sql users set-password college_app --instance=college-db --password="NEW"`; then `printf '%s' ... \| gcloud secrets versions add college-db-password --data-file=-`, then deploy | Brief errors are possible between changing the password and deploying; do it at a quiet time |
| Exam token secret | `openssl rand -hex 32`; `gcloud secrets versions add college-exam-token-secret --data-file=-`, then deploy | Students in the middle of an exam can't submit; do it when nobody is taking the exam |

The service uses the `latest` version of each secret, read when a container starts. Deploying makes every container restart with the new value. Disable old versions afterwards:

```bash
gcloud secrets versions disable <db-secret-name>
```

## Updating

### Python dependencies (every 1–3 months)

1. Create a branch. Raise the versions in `requirements.txt` and `requirements-dev.txt`. Check each project's changelog for breaking changes, especially FastAPI, SQLAlchemy, Pydantic and firebase-admin.
2. `pip install -r requirements-dev.txt && pytest && ruff check`
3. Open a pull request. CI runs everything, including PostgreSQL and the Docker build.
4. Merge, test on staging, then release to production.

GitHub **Dependabot** can open these pull requests automatically: **Settings → Code security → Dependabot version updates**.

### Python version

The image uses `python:3.12-slim`. To move to a newer Python:

- Change `FROM` in the `Dockerfile` and `python-version` in both workflow files.
- Run the tests.
- Deploy to staging first.

### Database (Cloud SQL)

- **Minor PostgreSQL updates** are applied automatically in the maintenance window (Monday 02:30 IST). A restart of a few seconds is possible.
- **Major version upgrades** (e.g. 16 → 17):

  ```bash
  gcloud sql instances patch college-db --database-version=POSTGRES_17
  ```

  1. Test on staging first.
  2. Take a manual backup.
  3. Upgrade production at a quiet time.

## Monitoring and alerts

**Logs:** Cloud Console → Cloud Run → `college-api` → **Logs**. Every request is logged with method, path, status, duration and a `request_id`. The same `request_id` is in the error response the user sees, so you can find exactly what happened.

Useful log searches (Logs Explorer):

| Find | Query |
|---|---|
| Server errors | `resource.labels.service_name="college-api" severity>=ERROR` |
| Google Sheets problems | `resource.labels.service_name="college-api" jsonPayload.message:"Google Sheets"` |
| One user's error | `jsonPayload.request_id="<id from the error message>"` |

**Set up these alerts once** (Cloud Console → Monitoring → Alerting → **Create policy**; notify the maintainer's email):

1. **Uptime check:** Monitoring → Uptime checks → **Create**. HTTPS, host = your domain, path `/api/v1/readyz`, every 5 minutes. Alert when it fails.
2. **Server errors:** metric **Cloud Run Revision → Request count**, filter `response_code_class = 5xx`, over 5 minutes.
3. **Sheets rows failing repeatedly:** Logs Explorer query `jsonPayload.message="Google Sheets row still failing"` → **Create alert**.
4. **Database:** **Cloud SQL → CPU utilisation** over 80% for 15 minutes; **Disk utilisation** over 80%.
5. **Budget:** billing budget alerts ([Firebase setup, step 11](04-firebase-setup.md#3-create-the-project)).

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Deploy fails: "still contains REPLACE_ME" | Fill in `config/{env}.env.yaml` ([Configuration](03-configuration.md)) |
| Service won't start: "Invalid configuration for production" | The log line lists exactly which settings are missing or unsafe |
| `/readyz` returns 503 | Database unreachable. Check the Cloud SQL instance is running, `CLOUD_SQL_CONNECTION_NAME` is right, the `college-api` service account has **Cloud SQL Client**, and the `college-db-password` secret matches |
| Migration job fails | Cloud Run → Jobs → `college-migrate` → Logs. If the password changed, redeploy; the service is not changed until migrations succeed |
| Admin gets "This account does not have admin access" | The Firebase UID/email do not match the sole `admin_users` record. Do not add another account; inspect the existing registration through the approved recovery process. |
| Admin gets "Your email address is not verified" | Verify the existing Firebase account's email. The registration command will not modify Firebase users. |
| Students get "App verification failed" | App Check site key or domain mismatch. Check the reCAPTCHA key domains and the App Check registration ([Firebase setup, step 3](04-firebase-setup.md#3-app-check-blocks-bots-from-the-public-forms)) |
| Students never receive the SMS | Domain missing from **Authorized domains**, SMS region policy not allowing India, or Firebase SMS quota reached (Authentication → Usage) |
| "Your OTP verification has expired" | The student took more than 10 minutes between OTP and submit. They verify again. Adjust `OTP_MAX_AGE_SECONDS` if needed |
| Rows missing in Google Sheets | Check the Sheets service account access and Cloud Run logs. Retry the student action after Sheets is available. |
| "The mock exam is not available right now" | No exam set uploaded. Upload at least one |
| Exam upload rejected | The response lists every problem with its row number. Fix the Excel file ([format](10-exam-question-format.md)) |
| Website shows old content | The CDN caches the content for 60 seconds. Wait a minute |
| 429 "Too many attempts" | Rate limit per IP. Wait the number of seconds in `Retry-After` |
