# 9. API reference (for the frontend team)

- **Interactive docs with every field:** `/docs` on local and staging (off in production).
- **Machine-readable spec:** `/openapi.json`. Generate a typed client from it, e.g. with `openapi-typescript`.
- **Base URL:** `https://<site-domain>/api/v1/`, through the Firebase Hosting rewrite. All bodies are JSON unless stated.

## Headers

| Header | When |
|---|---|
| `Authorization: Bearer <Firebase ID token>` | Every `/api/v1/admin/**` call. Use `await auth.currentUser.getIdToken()`; the SDK refreshes it |
| `X-Firebase-AppCheck: <token>` | `POST /brochures/{course}/download` and `POST /exam/start`. Use `(await getToken(appCheck)).token` |
| `X-Request-ID` | Optional. Echoed back, and included in logs |

## Errors

Every error has the same shape (content type `application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Validation failed",
  "status": 422,
  "code": "MOBILE_MISMATCH",
  "detail": "The verified mobile number does not match the number in the form.",
  "request_id": "6f1c..."
}
```

- Show `detail` to the user. Branch on `code`.
- Field errors add `"errors": [{"field": "mobile", "message": "..."}]`.
- 429 responses add `retry_after_seconds` and a `Retry-After` header.
- Mention `request_id` when reporting a problem.

| Code | Status | Meaning |
|---|---:|---|
| `VALIDATION_FAILED` | 422 | Fields invalid (see `errors`) |
| `UNAUTHENTICATED`, `TOKEN_INVALID`, `TOKEN_EXPIRED`, `TOKEN_REVOKED` | 401 | Sign in (admin) or verify OTP again (student) |
| `APP_CHECK_FAILED` | 401 | App Check token missing or invalid. Reload the page |
| `OTP_REQUIRED`, `OTP_EXPIRED` | 401 | Student must (re)verify the mobile number |
| `MOBILE_MISMATCH` | 422 | Number in the form differs from the verified one |
| `NOT_AN_ADMIN`, `EMAIL_NOT_VERIFIED` | 403 | Admin access problems |
| `NOT_FOUND`, `COURSE_NOT_FOUND`, `BROCHURE_NOT_FOUND` | 404 | |
| `SLOT_OCCUPIED` | 409 | Delete the existing exam set first |
| `TOKEN_EXPIRED`, `SET_REPLACED` | 410 | Exam attempt no longer valid. Start a new one |
| `INVALID_IMAGE`, `INVALID_PDF`, `INVALID_EXCEL`, `INVALID_QUESTION_SET`, `INVALID_VIDEO_LINK`, `FEE_BREAKUP_MISMATCH` | 422 | Upload or field problems |
| `PAYLOAD_TOO_LARGE` | 413 | File too big |
| `RATE_LIMITED` | 429 | Too many attempts |
| `NO_EXAM_SETS` | 503 | No exam setup uploaded yet |

## Public website

### `GET /public/site`

Everything the home page shows, in one call. It's cached for 60 seconds by the CDN.

```json
{
  "settings": {
    "phone": "...",
    "whatsapp": "...",
    "email": "...",
    "address": "...",
    "google_form_url": "...",
    "social_links": {
      "facebook": null,
      "instagram": "...",
      "youtube": "...",
      "linkedin": null
    }
  },
  "banners": [{
    "id": "...",
    "title": "PGDM Admissions Open",
    "image_url": "...",
    "thumb_url": "...",
    "image_width": 1920,
    "image_height": 768,
    "brochure_course_code": "PGDM"
  }],
  "announcements": [{
    "id": "...",
    "message": "Admissions open for 2026",
    "link_url": null
  }],
  "courses": [{
    "code": "ADV_BCOM",
    "name": "Advance B.Com",
    "duration_text": "3 years",
    "eligibility": null,
    "total_fee_inr": 300000,
    "total_fee_display": "₹3,00,000",
    "fee_note": null,
    "fee_breakup": [{
      "label": "Year 1",
      "amount_inr": 100000,
      "amount_display": "₹1,00,000"
    }],
    "has_brochure": true,
    "batches": [{
      "id": "...",
      "start_date": "2027-06-15",
      "end_date": "2030-04-30",
      "timings": "9:30 AM - 4:30 PM",
      "mode": "offline"
    }]
  }],
  "gallery": [{
    "id": "...",
    "caption": "Annual day",
    "image_url": "...",
    "thumb_url": "...",
    "image_width": 1600,
    "image_height": 1067
  }],
  "videos": [{
    "id": "...",
    "title": "Campus tour",
    "platform": "youtube",
    "url": "...",
    "embed_url": "https://www.youtube-nocookie.com/embed/<id>",
    "video_id": "<id>"
  }],
  "exam": {
    "available": true,
    "duration_minutes": 150,
    "total_questions": 200,
    "sections": {"A": 75, "B": 75, "C": 50}
  },
  "generated_at": "2026-10-30T10:00:00Z"
}
```

Display notes:

- **Banner button:** show it only when `brochure_course_code` is set. Clicking it opens the registration form, then downloads that course's brochure.
- **Fees:** show `total_fee_display`. If `fee_breakup` is not empty, also list each `label` and `amount_display`.
- **Contact management:** next to batches, use `settings.phone`, `settings.whatsapp` or `settings.email`.
- **Videos:** `platform` is `youtube`, `youtube_short` or `instagram_reel`. Put `embed_url` in an `<iframe>`. Shorts and Reels are portrait (9:16); YouTube videos are 16:9.
- **Inquiry:** link or embed `settings.google_form_url`. The Google Form stores answers in its own Google Sheet; it is not part of this API.

### `GET /registration/options`

Dropdown values: `qualifications`, `years_passed_out` (first item is "Currently Pursuing"), and `states` (36 states and union territories).

## The registration form + OTP (used by brochure download and exam)

Fields (same for both):

| Field | Required | Rules |
|---|---|---|
| `name` | yes | 2–100 characters, no digits |
| `mobile` | yes | Indian mobile. `9876543210`, `+91 98765 43210`, etc. are accepted |
| `email` | no | Valid email or empty |
| `highest_qualification` | no | One of `qualifications` |
| `year_passed_out` | no | One of `years_passed_out` |
| `city` | no | Free text, max 100 |
| `state` | no | One of `states` |
| `firebase_id_token` | yes | From Firebase Phone Auth (below) |

**OTP every time:** the student verifies the mobile number by OTP for **each** brochure download and **each** exam start. The token must be less than 10 minutes old.

```js
import { getAuth, RecaptchaVerifier, signInWithPhoneNumber, signOut } from "firebase/auth";
import { getToken } from "firebase/app-check";

const auth = getAuth();
const verifier = new RecaptchaVerifier(auth, "otp-button", { size: "invisible" });
const confirmation = await signInWithPhoneNumber(auth, "+91" + form.mobile, verifier); // SMS sent
const credential = await confirmation.confirm(codeTypedByStudent); // code checked
const firebaseIdToken = await credential.user.getIdToken();
const appCheckToken = (await getToken(appCheck)).token;
await signOut(auth); // the student does not stay signed in
```

## Brochure download

`POST /brochures/{course_code}/download`

- `course_code` is `IBFAP`, `ADV_BCOM` or `PGDM`.
- Headers: `X-Firebase-AppCheck`.
- Body: the registration form.

Response `200` is **the PDF file itself** (`application/pdf`, with a `Content-Disposition` filename). The details are recorded in the "Brochure Downloads" sheet.

```js
const res = await fetch(`/api/v1/brochures/${code}/download`, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-Firebase-AppCheck": appCheckToken },
  body: JSON.stringify({ ...form, firebase_id_token: firebaseIdToken }),
});
if (!res.ok) throw await res.json();
const blob = await res.blob();
const link = Object.assign(document.createElement("a"), {
  href: URL.createObjectURL(blob),
  download: `${code}-brochure.pdf`
});
link.click();
```

## Mock exam

### `GET /exam/info`

Returns `{available, duration_minutes, total_questions, sections}`. If `available` is false, hide the "Take the exam" button.

### `POST /exam/start`

- Headers: `X-Firebase-AppCheck`.
- Body: the registration form.

The details are recorded in the "Exam Registrations" sheet. A random one of the uploaded sets is chosen.

```json
{
  "attempt_token": "eyJ...",
  "set_name": "Mock Test 1",
  "duration_seconds": 9000,
  "started_at": "2026-10-30T10:00:00Z",
  "ends_at": "2026-10-30T12:30:00Z",
  "total_questions": 200,
  "sections": [
    {
      "code": "A",
      "title": "Analytical Ability",
      "question_count": 75,
      "items": [{
        "type": "question",
        "question": {
          "id": "q-uuid",
          "number": 1,
          "subsection": "Problem Solving",
          "content": [{"type": "text", "text": "Find the missing number: 4, 9, 19, 39, 79, ?"}],
          "options": [
            {"id": "o-uuid", "content": "159"},
            {"id": "...", "content": "119"},
            {"id": "...", "content": "169"},
            {"id": "...", "content": "139"}
          ]
        }
      }]
    },
    {
      "code": "C",
      "title": "Communication Ability",
      "question_count": 50,
      "items": [{
        "type": "passage",
        "passage": {"id": "p-uuid", "content": [{"type": "text", "text": "Saving early..."}]},
        "questions": [{
          "id": "...",
          "number": 151,
          "subsection": "Reading Comprehension",
          "content": [],
          "options": []
        }]
      }]
    }
  ]
}
```

How to render it:

- **Sections** always come in the order A, B, C. Inside a section the order is already shuffled; show items in the order given.
- **Option labels:** label options A-D yourself, in the order given. The options are already shuffled.
- **`number`** runs from 1 to 200 across the whole paper; use it for the question palette.
- **`content`** is a list of blocks:
  - `{"type": "text", "text": "..."}`: keep line breaks.
  - `{"type": "table", "header": ["Year", "Sales"], "rows": [["2023", "450"]]}`: render as a table.
- **Passage items** show the passage once, then its `questions`.
- **No answers** are in this response.

**Saving progress (required: refresh must resume):**

- After `start`, save `{attempt_token, ends_at, sections, answers: {}}` in `localStorage`.
- Update `answers` on every click.
- On page load, if a saved attempt exists and `ends_at` is in the future, resume it.
- Compute the timer from `ends_at` (not a counter), so it stays correct after a refresh.
- **Auto-submit when `ends_at` is reached.** The server accepts submissions up to 5 minutes after `ends_at`.
- Clear the saved attempt after a successful submit.

### `POST /exam/submit`

```json
{
  "attempt_token": "eyJ...",
  "answers": [
    {"question_id": "q-uuid", "option_id": "o-uuid"},
    {"question_id": "q-uuid-2", "option_id": null}
  ]
}
```

Unanswered questions can be sent with `option_id: null` or left out. Nothing is stored. Response:

```json
{
  "set_name": "Mock Test 1",
  "total_score": 132,
  "max_score": 200,
  "correct": 132,
  "incorrect": 50,
  "unanswered": 18,
  "submitted_after_time_limit": false,
  "sections": [{
    "code": "A",
    "title": "Analytical Ability",
    "score": 50,
    "max_score": 75,
    "correct": 50,
    "incorrect": 20,
    "unanswered": 5
  }],
  "review": [{
    "question_id": "q-uuid",
    "section": "A",
    "selected_option_id": "o-uuid",
    "correct_option_id": "o-uuid-2",
    "status": "incorrect",
    "is_correct": false
  }]
}
```

Use `review` with the saved paper to show each question with the student's choice and the correct option highlighted.

## Admin API (all under `/api/v1/admin`, Bearer token required)

| Method and path | Purpose |
|---|---|
| `GET /me` | Check access after sign-in (403 code: `NOT_AN_ADMIN`) |
| `GET`, `PUT /site-settings` | Contact details and links (PUT replaces all fields) |
| `GET /courses`, `GET /courses/{code}`, `PATCH /courses/{code}` | Course details and fees. `fee_breakup` must add up to `total_fee_inr` (send `[]` to show the total only) |
| `GET /batches?course=PGDM`, `POST /batches`, `PATCH /batches/{id}`, `DELETE /batches/{id}` | Batches: `course_code`, `start_date`, `end_date`, `timings`, `mode` (`online` or `offline`), `is_active` |
| Brochure management | Unavailable until the approved `brochures` metadata schema exists |
| `GET /banners`, `POST /banners` (multipart: `title`, `course_code`?, `display_order`, `is_active`, `image`), `PATCH /banners/{id}`, `PUT /banners/{id}/image`, `DELETE /banners/{id}` | Banners. `course_code: null` removes the brochure button |
| `GET /announcements`, `POST`, `PUT /announcements/{id}`, `DELETE /announcements/{id}` | `message`, `link_url`, `starts_at`, `ends_at`, `display_order`, `is_active` |
| Gallery management | Unavailable until the approved `gallery_images` metadata schema exists |
| `GET /videos`, `POST /videos` (multipart: `title`, `url` (YouTube, Shorts or Instagram Reel), `display_order`, `is_active`), `PATCH /videos/{id}`, `DELETE /videos/{id}` | Videos |
| `GET /exam/sets` | The 3 slots and what's in them |
| `GET /exam/template` | Download the Excel template |
| `POST /exam/sets/validate` (multipart `file`) | Check a file without saving it. Returns counts, errors and warnings |
| `POST /exam/sets/{slot}` (multipart `file`, `name`?) | Upload into an empty slot (1–3). On problems: 422 with `report.errors` (row numbers) |
| `PUT /exam/sets/{slot}` (multipart `file`, `name`?) | Atomically replace a populated slot; a failed replacement preserves the current set |
| `DELETE /exam/sets/{slot}` | Empty a slot |
| Lead retry dashboard | Unavailable until the approved `pending_sheet_rows` schema exists |

**Images:** JPEG, PNG or WebP, up to 10 MB, are converted to WebP in two sizes: `image_url` (max 1920 px wide) and `thumb_url` (max 600 px).

## Admin Email/Password sign-in (frontend outline)

```js
import { getAuth, signInWithEmailAndPassword } from "firebase/auth";

const credential = await signInWithEmailAndPassword(auth, email, password);
const idToken = await credential.user.getIdToken();
```

The backend accepts the Firebase ID token only when its provider is `password`,
the email is verified, and its UID/email match the one active `admin_users` row.

## Limits

| What | Limit |
|---|---|
| Brochure downloads | 20 per hour per IP address |
| Exam starts | 1 per hour per IP address |
| Exam submits | 30 per hour per IP address |
| Upload sizes | Images 10 MB, PDFs 25 MB, Excel 5 MB |

