# 5. Google Sheets setup

Student details from **brochure downloads** and **exam registrations** go to one Google spreadsheet with two tabs. The backend writes to it using its own Google identity (the Cloud Run service account), so no passwords or key files are needed.

Use **one spreadsheet per environment**, e.g. "College Leads (Staging)" and "College Leads". Then test data never mixes with real data.

## 1. Create the spreadsheet

1. In the **college's** Google account, create a new Google Sheet, e.g. "College Leads".
2. Rename the first tab to exactly **Brochure Downloads**.
3. Add a second tab named exactly **Exam Registrations**.
4. Leave both tabs empty. The backend writes the header row automatically on the first submission:

| Tab | Columns |
|---|---|
| Brochure Downloads | Submitted At (IST), Name, Mobile, Email, Highest Qualification, Year Passed Out, City, State, Course |
| Exam Registrations | Submitted At (IST), Name, Mobile, Email, Highest Qualification, Year Passed Out, City, State, Exam Set |

If you prefer different tab names, set `SHEETS_TAB_BROCHURE` and `SHEETS_TAB_EXAM` to match.

## 2. Share it with the backend

1. Click **Share**.
2. Add the runtime service account as an **Editor**:
   - Production: `college-api@college-prod.iam.gserviceaccount.com`
   - Staging: `college-api@college-staging.iam.gserviceaccount.com`
3. Untick "Notify people". The address is not a mailbox.

## 3. Tell the backend which sheet to use

1. Copy the spreadsheet ID from its URL: `https://docs.google.com/spreadsheets/d/<ID>/edit`.
2. Put it in `SHEETS_SPREADSHEET_ID` in `config/production.env.yaml` (or `staging`).
3. Make sure the **Google Sheets API** is enabled in the project ([Google Cloud setup](06-google-cloud-setup.md), step 2).
4. Deploy.

## 4. Test

Download a brochure on the staging site. A new row should appear within a few seconds.

If it doesn't:

- **Check the logs:** Cloud Console → Cloud Run → `college-api` → Logs. Search for "Google Sheets".
- `403` means the sheet isn't shared with the service account, or the Sheets API is off.
- `400 Unable to parse range` means the tab name doesn't match exactly.
- **Current PlanetFiance behavior:** exam registrations are written directly to Google Sheets. If Sheets is unavailable, the exam start is refused so the student can retry; the retry queue awaits a separately approved `pending_sheet_rows` schema.

## Good to know

- Values are written as plain text, so a name like `=SUM(A1)` can never become a formula.
- Mobile numbers are written as text, so leading zeros are preserved.
- The admin can sort, filter, colour, archive or delete rows freely. The backend only ever adds new rows at the bottom.
- **Don't rename the tabs** while the site is live without changing the setting and redeploying.
- **Google Sheets has a limit of 10 million cells per spreadsheet.** At 9 columns that's about 1 million rows, which is many years at this volume. Archive yearly anyway.
- **Backup:** Google keeps version history ("File → Version history"). Also download a copy monthly ("File → Download → Excel"). See [Operations](08-operations.md).
