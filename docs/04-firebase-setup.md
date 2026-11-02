# 4. Firebase setup

Do this once for **staging** (`college-staging`) and once for **production** (`college-prod`).
The Firebase project and the Google Cloud project are the same project.

## 1. Create the project

1. Go to <https://console.firebase.google.com>, then **Add project**. Name it `college-prod` (or pick the existing Google Cloud project of that name).
2. Google Analytics: you can link the Google Analytics property here.
3. **Upgrade to the Blaze (pay-as-you-go) plan:** ⚙ → **Usage and billing** → **Details & settings** → **Modify plan**. Use the **college's** billing account. Blaze is required for Cloud Run, phone SMS and storage.
4. Set a budget alert: Google Cloud Console → **Billing** → **Budgets & alerts** → create a monthly budget with email alerts at 50%, 90% and 100%.

## 2. Authentication

1. Firebase Console → **Authentication** → **Get started**.
2. **Sign-in method:**
   - Enable **Email/Password**. This is the administrator sign-in provider. Do not enable Email link for the admin portal.
   - Enable **Phone**. This is for student OTP.
3. **Authorized domains** (Settings → Authorized domains): add the website domains, e.g. `college.com` and `www.college.com`. Phone sign-in only works on these domains.
4. **SMS region policy** (Settings → SMS region policy): choose **Allow** and select **India** only. This blocks SMS fraud to foreign numbers.
7. **Staging only, test phone numbers:** Sign-in method → Phone → Phone numbers for testing. Add e.g. `+91 99999 00001` with code `123456`. Testers then receive no real SMS and it costs nothing.

## Creating the admin account

After the backend is deployed ([Deployment](07-deployment.md)), run:

```bash
./scripts/run-cli.sh production grant-existing-admin --email admin@college.com --name "College Admin"
```

Before running it, ensure the intended administrator has an existing Firebase
Email/Password account and that their email is verified. The
command then does only this:

- Reads the existing Firebase account and requires its email to already be verified.
- Creates the sole backend **admin allow-list** record. It refuses if any `admin_users` record already exists.

It never creates, verifies, resets, disables, or otherwise changes a Firebase user.

Then:

1. The administrator signs in with their Firebase Email/Password credentials. The application has no public password-reset flow.
2. Sign in to the admin portal with that registered email address.

There is no normal deactivation, replacement, or password-reset command: this
is a one-admin system. Handle a lost-account incident through an approved
security recovery procedure, not from the dashboard or a public API.

## 3. App Check (blocks bots from the public forms)

1. Google Cloud Console → **Security → reCAPTCHA** → **Create key**.
   - Type: **Website**.
   - Domains: your site domains, plus `localhost` for staging only.
2. Firebase Console → **App Check** → **Apps** → your web app → **reCAPTCHA Enterprise** → paste the key → **Save**.
3. The frontend initialises App Check with the same site key and sends the token in the `X-Firebase-AppCheck` header. The backend verifies it (`APP_CHECK_ENABLED=true`).
4. **Enforcement** (**App Check → APIs**): you can also enforce App Check for **Authentication**. Do this only after the website is live and the App Check metrics show the real site's traffic is verified.

## 4. Storage

1. Firebase Console → **Storage** → **Get started**.
   - Location: **`asia-south1` (Mumbai)**. This can't be changed later.
   - Start in **production mode**.
2. The bucket is called `<project-id>.firebasestorage.app`. Put that name in `STORAGE_BUCKET` in `config/<env>.env.yaml`.
3. **Security rules:** the browser never talks to Storage directly; only the backend does, with its service account. Replace the rules with "deny all" (Storage → Rules):

   ```text
   rules_version = '2';
   service firebase.storage {
     match /b/{bucket}/o {
       match /{allPaths=**} {
         allow read, write: if false;
       }
     }
   }
   ```

   Public images still load. Their URLs include a download token created by the backend, which works regardless of these rules. Brochure PDFs have no such token, so they can only be fetched through the API after OTP.
4. Turn on versioning and keep deleted files for 30 days (protection against mistakes):

   ```bash
   gcloud storage buckets update gs://college-prod.firebasestorage.app --versioning --soft-delete-duration=30d
   ```

## 5. Frontend web app and Hosting

Not part of this backend, but the frontend team needs these:

1. Firebase Console → ⚙ **Project settings** → **Your apps** → **Add app → Web**. Copy the config object into the frontend.
2. In the frontend's `firebase.json`, forward the API to Cloud Run. The `/api/**` rule must come before the SPA catch-all:

   ```json
   {
     "hosting": {
       "public": "dist",
       "rewrites": [
         { "source": "/api/**", "run": { "serviceId": "college-api", "region": "asia-south1" } },
         { "source": "**", "destination": "/index.html" }
       ]
     }
   }
   ```

3. Connect the custom domain: **Hosting → Add custom domain**. Add the records it shows at the domain registrar. Don't touch the existing email (MX) records.

How the frontend uses Auth, App Check and the API: [API reference](09-api-reference.md).
