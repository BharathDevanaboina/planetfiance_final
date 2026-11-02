# 7. Deployment and CI/CD

## How it works

``` mermaid
flowchart LR
    pr["Pull request"] --> ci["CI workflow\nlint, tests (SQLite + PostgreSQL),\nmigration checks, Docker build"]
    main["Merge to main"] --> stg["Deploy workflow\nstaging (automatic)"]
    manual["Run workflow manually\nenvironment = production"] --> approve["Approval by a reviewer"] --> prod["production"]
```

Every deployment, whether automatic or by hand, runs
`scripts/deploy.sh`, which:

1.  Builds the container image and pushes it to Artifact Registry.
2.  Runs only the PlanetFiance existing-database migration target (`alembic upgrade planetfiance_existing@head`) as the Cloud
    Run job `college-migrate`.
3.  Deploys the new image to the Cloud Run service `college-api`.
4.  Calls `/api/v1/readyz`. If that fails, it **moves traffic back to
    the previous version automatically** and stops with an error.

## 1. Before the first deployment

-   [ ] [Firebase setup](04-firebase-setup.md) done (Auth, App Check,
    Storage).
-   [ ] [Google Sheets setup](05-google-sheets-setup.md) done.
-   [ ] [Google Cloud setup](06-google-cloud-setup.md) steps 1--8 done.
-   [ ] No `REPLACE_ME` left in `config/.env.example` (or the production
    environment configuration).

## 2. Connect GitHub Actions (once)

1.  Push this code to a GitHub repository (the one named in
    `GITHUB_REPO` during setup).

2.  GitHub → repository → **Settings → Environments** → create two
    environments: **staging** and **production**.

3.  In **each** environment, add these **variables** (not secrets),
    using the values printed in [Google Cloud setup, step
    7](06-google-cloud-setup.md#7-keyless-login-for-github-actions-workload-identity)
    for that project:

      -------------------------------------------------------------------------------------------------------------------------------------
      Variable                            Example
      ----------------------------------- -------------------------------------------------------------------------------------------------
      `GCP_WORKLOAD_IDENTITY_PROVIDER`    `projects/123456789012/locations/global/workloadIdentityPools/github/providers/github-provider`

      `GCP_DEPLOY_SERVICE_ACCOUNT`        `college-deployer@college-prod.iam.gserviceaccount.com`
      -------------------------------------------------------------------------------------------------------------------------------------

4.  Protect production: environment **production** → **Required
    reviewers** → add the people allowed to approve releases.
    Optionally, limit **Deployment branches** to `main`.

5.  Protect `main`: **Settings → Branches → Add rule** → require a pull
    request and require the **CI** checks to pass.

## 3. Deploy

### Staging (automatic)

Merge a pull request into `main`. Watch progress under **Actions →
Deploy**.

### Production

1.  Check the change on staging.
2.  GitHub → **Actions → Deploy → Run workflow** → branch `main`,
    environment **production** → **Run**.
3.  A reviewer approves it. The workflow runs the tests again, then
    deploys.

### By hand (without GitHub)

Requirements: `gcloud` (logged in, with deploy rights on the project)
and Docker.

``` bash
gcloud auth login
./scripts/deploy.sh staging       # or: production
```

### Very first deployment

Do the first deployment by hand (above) or through the workflow. Then:

1.  [Google Cloud setup, step
    9](06-google-cloud-setup.md#9-scheduler-job-after-the-first-deployment)
    (scheduler).
2.  Create the admin account ([Firebase
    setup](04-firebase-setup.md#creating-the-admin-account)).
3.  Ask the frontend team to deploy Firebase Hosting with the `/api/*`
    rewrite ([Firebase setup, step
    5](04-firebase-setup.md#5-frontend-web-app-and-hosting)).
4.  Smoke test:
    -   `https://<your-domain>/api/v1/healthz` and
        `https://<your-domain>/api/v1/readyz` both return `ok`.
    -   Admin portal: sign in, change a site setting, then see it on the
        website within 1 minute.
    -   Upload brochures and exam sets.
    -   On the website: download a brochure with a real mobile number,
        and check the row in Google Sheets.

## 4. Roll back

**Fast (seconds), no rebuild:** Cloud Console → Cloud Run →
`college-api` → **Revisions** → pick the previous revision → **Manage
traffic** → 100%. Or:

``` bash
gcloud run revisions list --service=college-api --region=asia-south1
gcloud run services update-traffic college-api --region=asia-south1 --to-revisions=<REVISION_NAME>=100
```

Notes: - Traffic stays pinned to that revision until the next deploy. -
After fixing the problem, deploy normally. `gcloud run deploy` sends all
traffic to the new revision.

**Database changes:** migrations are written to be backwards compatible
(see [Local development --- Changing the
database](02-local-development.md#changing-the-database)), so the
previous app version runs fine on the newer schema. You normally do
**not** undo a migration. If you really must, take a backup first, then
undo the latest migration:

``` bash
gcloud sql backups create --instance=college-db --description="before downgrade"
gcloud run jobs execute college-migrate --region=asia-south1 --args=downgrade,-1 --wait
```

The next normal existing-database deploy runs `upgrade planetfiance_existing@head` again, so remove or fix the
migration in Git first.

## 5. What is deployed where

  -----------------------------------------------------------------------
                          Staging                 Production
  ----------------------- ----------------------- -----------------------
  Project                 `college-staging`       `college-prod`

  Cloud Run service       `college-api` (e-2      `college-api` (1-5
                          containers)             containers, 1 always
                                                  warm)

  Database                `college-db` (small)    `college-db` (backups +
                                                  PITR)

  Trigger                 every push to `main`    manual + approval

  SMS                     test phone numbers      real SMS
  -----------------------------------------------------------------------

## 6. Changing settings or scaling

-   **Settings:** edit `config/.env.yaml`, merge, deploy.
-   **Size and scaling:** edit `config/env.deploy.env` (`MIN_INSTANCES`,
    `MAX_INSTANCES`, `CPU`, `MEMORY`), then deploy.
-   **Admission-based scaling:** raise `MAX_INSTANCES` (for example to
    10), and make sure the database allows `MAX_INSTANCES × 10`
    connections. A `db-custom-1-3840` instance allows about 100.
