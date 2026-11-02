import { initializeApp } from "https://www.gstatic.com/firebasejs/11.0.2/firebase-app.js";
import {
  getAuth,
  onAuthStateChanged,
  GoogleAuthProvider,
  signInWithPopup,
  signOut,
} from "https://www.gstatic.com/firebasejs/11.0.2/firebase-auth.js";

const root = document.querySelector("#app");
const toastRegion = document.querySelector("#toast-region");
const state = { auth: null, user: null, page: "dashboard", cache: {}, visualPreview: false };
const nav = [
  ["dashboard", "◫", "Overview"], ["settings", "⚙", "Contact & settings"],
  ["courses", "◈", "Courses & fees"], ["batches", "◷", "Batches"],
  ["brochures", "▣", "Brochures"], ["banners", "▧", "Banners"],
  ["announcements", "◉", "Announcements"], ["gallery", "▦", "Gallery"],
  ["videos", "▶", "Videos"], ["exam", "✦", "Mock exam"], ["leads", "⌁", "Lead delivery"],
];

// This route is deliberately restricted to a local browser and is only for
// inspecting the already-built administration UI. It never initializes
// Firebase, sends an API request, or changes the real sign-in flow.
const localVisualPreview = ["127.0.0.1", "localhost", "::1"].includes(window.location.hostname)
  && new URLSearchParams(window.location.search).get("preview") === "1";
const previewImage = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='260' viewBox='0 0 640 260'%3E%3Crect width='640' height='260' fill='%23154432'/%3E%3Ccircle cx='540' cy='45' r='120' fill='%2327a77a' opacity='.35'/%3E%3Ctext x='42' y='128' fill='white' font-family='Arial' font-size='36' font-weight='700'%3EPlanetFiance%3C/text%3E%3Ctext x='42' y='168' fill='%23cfeadf' font-family='Arial' font-size='20'%3EAdmissions open%3C/text%3E%3C/svg%3E";
const previewData = {
  settings: { phone: "+91 98765 43210", whatsapp: "+91 98765 43210", email: "admissions@planetfiance.example", google_form_url: "https://forms.google.com/", address: "PlanetFiance College, Hyderabad", social_links: { facebook: "https://facebook.com/", instagram: "https://instagram.com/", youtube: "https://youtube.com/", linkedin: "https://linkedin.com/", x: "" } },
  courses: [
    { code: "IBFAP", name: "IBFAP", duration_text: "3 years", summary: "Integrated banking, finance and accounting programme.", eligibility: "12th standard or equivalent", total_fee_inr: 180000, fee_note: "Installments available.", fee_breakup: [{ label: "Year 1", amount_inr: 60000 }, { label: "Year 2", amount_inr: 60000 }, { label: "Year 3", amount_inr: 60000 }], display_order: 1, is_active: true },
    { code: "ADV_BCOM", name: "Advance B.Com.", duration_text: "3 years", summary: "Commerce degree with professional-skills support.", eligibility: "12th standard or equivalent", total_fee_inr: 150000, fee_note: null, fee_breakup: [{ label: "Year 1", amount_inr: 50000 }, { label: "Year 2", amount_inr: 50000 }, { label: "Year 3", amount_inr: 50000 }], display_order: 2, is_active: true },
    { code: "PGDM", name: "PGDM", duration_text: "2 years", summary: "Postgraduate diploma in management.", eligibility: "Graduation", total_fee_inr: 220000, fee_note: "Subject to admission criteria.", fee_breakup: [{ label: "Year 1", amount_inr: 110000 }, { label: "Year 2", amount_inr: 110000 }], display_order: 3, is_active: true },
  ],
  batches: [
    { id: "preview-batch-1", course_code: "IBFAP", course_name: "IBFAP", start_date: "2026-06-01", end_date: "2027-05-31", timings: "10:00 AM – 1:00 PM", mode: "offline", is_active: true },
    { id: "preview-batch-2", course_code: "PGDM", course_name: "PGDM", start_date: "2027-01-10", end_date: "2028-01-09", timings: "6:00 PM – 8:30 PM", mode: "online", is_active: true },
  ],
  banners: [{ id: "preview-banner-1", title: "Admissions open for 2026", course_code: "IBFAP", image_url: previewImage, thumb_url: previewImage, image_width: 640, image_height: 260, display_order: 1, is_active: true }],
  announcements: [{ id: "preview-announcement-1", message: "Admissions are open. Talk to our counsellors today.", link_url: "https://forms.google.com/", starts_at: "2026-11-01T00:00:00Z", ends_at: "2026-12-31T23:59:59Z", display_order: 1, is_active: true }],
  videos: [{ id: "preview-video-1", title: "Campus life at PlanetFiance", platform: "youtube", url: "https://www.youtube.com/watch?v=dQw4w9WgXcQ", embed_url: "https://www.youtube.com/embed/dQw4w9WgXcQ", video_id: "dQw4w9WgXcQ", display_order: 1, is_active: true }],
  examSets: [
    { slot: 1, exam_set: { slot: 1, name: "IBFAP practice set", question_count: 200, source_filename: "ibfap-preview.xlsx", uploaded_by: "local preview", created_at: "2026-11-02T00:00:00Z" } },
    { slot: 2, exam_set: { slot: 2, name: "Commerce practice set", question_count: 200, source_filename: "bcom-preview.xlsx", uploaded_by: "local preview", created_at: "2026-11-02T00:00:00Z" } },
    { slot: 3, exam_set: null },
  ],
};

const copyPreview = (value) => JSON.parse(JSON.stringify(value));
async function previewApi(path, { method = "GET", body } = {}) {
  if (path === "/admin/exam/sets/preview") return { report: { ok: true, question_count: 200, passage_count: 0, errors: [], warnings: [] }, questions: [] };
  if (method !== "GET") return body || null;
  const data = {
    "/admin/me": { email: "local-preview@planetfiance.invalid", role: "admin" },
    "/admin/site-settings": previewData.settings,
    "/admin/courses": previewData.courses,
    "/admin/batches": previewData.batches,
    "/admin/banners": previewData.banners,
    "/admin/announcements": previewData.announcements,
    "/admin/videos": previewData.videos,
    "/admin/exam/sets": previewData.examSets,
  };
  return copyPreview(data[path] ?? { report: { ok: true, question_count: 200, passage_count: 0, errors: [], warnings: [] }, questions: [] });
}

const escapeHtml = (value = "") => String(value).replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
const money = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
const date = (value) => value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium" }).format(new Date(value)) : "—";
const datetimeLocal = (value) => value ? new Date(value).toISOString().slice(0, 16) : "";
const status = (active, label = active ? "Active" : "Hidden") => `<span class="status ${active ? "good" : "muted"}">${label}</span>`;
const batchPhase = (batch) => { const today = new Date().toISOString().slice(0, 10); if (!batch.is_active) return status(false, "Hidden"); if (batch.end_date < today) return status(false, "Completed"); if (batch.start_date <= today) return status(true, "Running"); return `<span class="status warning">Upcoming</span>`; };

function notice(message, error = false) {
  const item = document.createElement("div"); item.className = `toast ${error ? "error" : ""}`; item.textContent = message;
  toastRegion.append(item); setTimeout(() => item.remove(), 4500);
}

function problem(error) {
  const detail = error?.detail || error?.message || "Something went wrong. Please try again.";
  notice(detail, true);
}

function loginProblem(error) {
  const messages = {
    "auth/configuration-not-found": "Firebase Google Sign-In is not configured for this project. Enable Google in Firebase Console → Authentication → Sign-in method.",
    "auth/popup-closed-by-user": "Google Sign-In was cancelled.",
    "auth/unauthorized-domain": "This domain is not authorised for Google Sign-In in Firebase.",
    "auth/user-disabled": "This Firebase account has been disabled.",
    "auth/too-many-requests": "Too many sign-in attempts. Please wait a moment and try again.",
  };
  notice(messages[error?.code] || error?.message || "Unable to sign in. Please try again.", true);
}

async function token() {
  if (!state.user) throw new Error("Your session has ended. Please sign in again.");
  return state.user.getIdToken();
}

async function api(path, { method = "GET", body, form = false } = {}) {
  if (state.visualPreview) return previewApi(path, { method, body, form });
  const headers = { Authorization: `Bearer ${await token()}` };
  if (body && !form) headers["Content-Type"] = "application/json";
  const response = await fetch(`/api/v1${path}`, { method, headers, body: body ? (form ? body : JSON.stringify(body)) : undefined });
  if (!response.ok) {
    let payload = {}; try { payload = await response.json(); } catch (_) { /* non-json response */ }
    const error = new Error(payload.detail || `Request failed (${response.status})`); Object.assign(error, payload); throw error;
  }
  if (response.status === 204) return null;
  const type = response.headers.get("content-type") || "";
  return type.includes("application/json") ? response.json() : response.blob();
}

async function secureFile(path, filename) {
  const preview = window.open("", "_blank");
  try {
    const blob = await api(path); const url = URL.createObjectURL(blob);
    if (preview) preview.location = url;
    else Object.assign(document.createElement("a"), { href: url, download: filename }).click();
    setTimeout(() => URL.revokeObjectURL(url), 60_000);
  } catch (error) { preview?.close(); problem(error); }
}

function modal(title, body, footer = "") {
  document.querySelector("#modal")?.remove();
  const el = document.createElement("div"); el.id = "modal"; el.className = "modal-backdrop";
  el.innerHTML = `<section class="modal" role="dialog" aria-modal="true" aria-label="${escapeHtml(title)}"><header class="modal-head"><h2>${escapeHtml(title)}</h2><button class="close" data-close-modal aria-label="Close">×</button></header><div class="modal-body">${body}</div>${footer ? `<footer class="modal-foot">${footer}</footer>` : ""}</section>`;
  el.addEventListener("click", (event) => { if (event.target === el || event.target.closest("[data-close-modal]")) el.remove(); }); document.body.append(el);
  return el;
}

function confirmAction(title, message, actionLabel = "Delete") {
  return new Promise((resolve) => {
    const el = modal(title, `<p style="margin:0;color:var(--muted);line-height:1.55">${escapeHtml(message)}</p>`, `<button class="button secondary" data-cancel>Cancel</button><button class="button danger" data-confirm>${escapeHtml(actionLabel)}</button>`);
    el.querySelector("[data-cancel]").onclick = () => { el.remove(); resolve(false); };
    el.querySelector("[data-confirm]").onclick = () => { el.remove(); resolve(true); };
  });
}

function loginScreen(message = "Sign in with the one authorized Google account.") {
  root.innerHTML = `<main class="auth-shell"><section class="auth-card"><div class="brand-mark">C</div><h1>College Control</h1><p>${escapeHtml(message)}</p><button class="button" id="google-sign-in" type="button">Continue with Google</button><p class="eyebrow" style="margin-top:16px">Only the registered Google account can access this dashboard.</p></section></main>`;
  root.querySelector("#google-sign-in").onclick = async () => {
    try { await signInWithPopup(state.auth, new GoogleAuthProvider()); }
    catch (error) { loginProblem(error); }
  };
}

function shell() {
  const initial = (state.user?.email || "A").slice(0, 1).toUpperCase();
  const previewBadge = state.visualPreview ? `<span class="status warning">Local visual preview</span>` : "";
  root.innerHTML = `<div class="shell"><aside class="sidebar"><div class="brand"><span class="brand-mark">C</span><span>College Admin</span></div><nav>${nav.map(([id, icon, label]) => `<button class="nav-item ${state.page === id ? "active" : ""}" data-page="${id}"><span class="nav-icon">${icon}</span><span>${label}</span></button>`).join("")}</nav><p class="sidebar-footer">${state.visualPreview ? "Sample data only. Nothing can be saved from this local preview." : "Securely connected to the existing FastAPI administration APIs."}</p></aside><main class="main"><header class="topbar"><div><strong>Administration</strong><div class="eyebrow">Content, admissions and student services</div></div><div class="user-menu">${previewBadge}<span class="user-email">${escapeHtml(state.user?.email || "")}</span><span class="avatar">${initial}</span><button class="text-button" id="sign-out">${state.visualPreview ? "Exit preview" : "Sign out"}</button></div></header><section id="page" class="page"><div class="loading"><div class="spinner"></div></div></section></main></div>`;
  root.querySelectorAll("[data-page]").forEach((button) => button.onclick = () => { state.page = button.dataset.page; shell(); renderPage(); });
  root.querySelector("#sign-out").onclick = () => state.visualPreview ? window.location.assign("/admin/") : signOut(state.auth);
}

const title = (heading, copy, action = "") => `<div class="page-title"><div><h1>${heading}</h1><p>${copy}</p></div>${action}</div>`;
const panel = (heading, body, action = "") => `<section class="panel"><header class="panel-head"><h2>${heading}</h2>${action}</header>${body}</section>`;
const table = (headers, rows, empty = "No records yet.") => `<div class="table-wrap"><table><thead><tr>${headers.map((h) => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows || `<tr><td colspan="${headers.length}" class="empty">${empty}</td></tr>`}</tbody></table></div>`;

async function renderPage() {
  const target = root.querySelector("#page");
  try {
    const pages = { dashboard, settings, courses, batches, brochures, banners, announcements, gallery, videos, exam, leads };
    await pages[state.page](target);
  } catch (error) {
    if (error.status === 401 || error.status === 403) { notice("Your administrator session is no longer authorized.", true); await signOut(state.auth); return; }
    target.innerHTML = `${title("Unable to load this page", "The API returned an error.")}<section class="panel"><div class="empty">${escapeHtml(error.detail || error.message)}</div></section>`;
  }
}

async function dashboard(target) {
  // Brochure metadata and the Google Sheets retry queue are intentionally not
  // queried until their missing database tables have separately been approved.
  const [courses, batches, sets] = await Promise.all([api("/admin/courses"), api("/admin/batches"), api("/admin/exam/sets")]);
  target.innerHTML = `${title("Welcome back", "Manage your website content and admissions operations from one place.")}<div class="grid cards"><div class="card metric"><small>Active courses</small><strong>${courses.filter((x) => x.is_active).length}</strong></div><div class="card metric"><small>Active batches</small><strong>${batches.filter((x) => x.is_active).length}</strong></div><div class="card metric"><small>Brochure metadata</small><strong style="font-size:17px">Not configured</strong></div><div class="card metric"><small>Lead retry queue</small><strong style="font-size:17px">Not configured</strong></div></div><div class="grid two-col" style="margin-top:18px">${panel("Exam-set readiness", `<div class="detail-list">${sets.map((item) => `<div><span>Question set ${item.slot}</span><strong>${item.exam_set ? `${item.exam_set.question_count} questions` : "Not uploaded"}</strong></div>`).join("")}</div>`, `<button class="button secondary small" data-page-link="exam">Manage sets</button>`)}${panel("Quick actions", `<div class="actions"><button class="button secondary" data-page-link="courses">Edit courses</button><button class="button secondary" data-page-link="banners">Manage banners</button></div>`)}</div>`;
  bindPageLinks(target);
}

async function settings(target) {
  const item = await api("/admin/site-settings");
  target.innerHTML = `${title("Contact & website settings", "Changes are saved to the existing site_settings database row.")}<section class="panel"><div class="panel-body"><form id="settings-form"><div class="form-grid"><div class="field"><label>Phone number</label><input name="phone" value="${escapeHtml(item.phone || "")}" /></div><div class="field"><label>WhatsApp number</label><input name="whatsapp" value="${escapeHtml(item.whatsapp || "")}" /></div><div class="field"><label>Email address</label><input name="email" type="email" value="${escapeHtml(item.email || "")}" /></div><div class="field"><label>Google Form link</label><input name="google_form_url" type="url" value="${escapeHtml(item.google_form_url || "")}" /></div><div class="field full"><label>College address</label><textarea name="address">${escapeHtml(item.address || "")}</textarea></div><div class="field"><label>Facebook URL</label><input name="facebook" value="${escapeHtml(item.social_links.facebook || "")}" /></div><div class="field"><label>Instagram URL</label><input name="instagram" value="${escapeHtml(item.social_links.instagram || "")}" /></div><div class="field"><label>YouTube URL</label><input name="youtube" value="${escapeHtml(item.social_links.youtube || "")}" /></div><div class="field"><label>LinkedIn URL</label><input name="linkedin" value="${escapeHtml(item.social_links.linkedin || "")}" /></div><div class="field"><label>X / Twitter URL</label><input name="x" value="${escapeHtml(item.social_links.x || "")}" /></div></div><div class="actions"><button class="button" type="submit">Save contact settings</button></div></form></div></section>`;
  target.querySelector("#settings-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); const social = Object.fromEntries(["facebook", "instagram", "youtube", "linkedin", "x"].map((k) => [k, f.get(k) || null])); try { await api("/admin/site-settings", { method: "PUT", body: { phone: f.get("phone") || null, whatsapp: f.get("whatsapp") || null, email: f.get("email") || null, address: f.get("address") || null, google_form_url: f.get("google_form_url") || null, social_links: social } }); notice("Contact settings saved."); } catch (error) { problem(error); } };
}

async function courses(target) {
  const items = await api("/admin/courses"); state.cache.courses = items;
  target.innerHTML = `${title("Courses & fees", "Edit the existing course records, information and year-wise fee structures.")}${panel("Course catalogue", table(["Course", "Duration", "Total fee", "Status", ""], items.map((item) => `<tr><td><strong>${escapeHtml(item.name)}</strong><br><small>${escapeHtml(item.code)}</small></td><td>${escapeHtml(item.duration_text)}</td><td>${money(item.total_fee_inr)}</td><td>${status(item.is_active)}</td><td><button class="button secondary small" data-edit-course="${item.code}">Edit</button></td></tr>`).join("")))}`;
  target.querySelectorAll("[data-edit-course]").forEach((button) => button.onclick = () => courseModal(items.find((x) => x.code === button.dataset.editCourse)));
}

function courseModal(item) {
  const fees = item.fee_breakup || [];
  const rows = fees.map((row) => feeRow(row.label, row.amount_inr)).join("");
  const el = modal(`Edit ${item.name}`, `<form id="course-form"><div class="form-grid"><div class="field"><label>Course name</label><input name="name" required value="${escapeHtml(item.name)}" /></div><div class="field"><label>Duration</label><input name="duration_text" required value="${escapeHtml(item.duration_text)}" /></div><div class="field"><label>Total fee (₹)</label><input name="total_fee_inr" required type="number" min="0" value="${item.total_fee_inr}" /></div><div class="field"><label>Display order</label><input name="display_order" required type="number" min="0" value="${item.display_order}" /></div><div class="field full"><label>Summary</label><textarea name="summary">${escapeHtml(item.summary || "")}</textarea></div><div class="field full"><label>Eligibility</label><textarea name="eligibility">${escapeHtml(item.eligibility || "")}</textarea></div><div class="field full"><label>Fee note</label><input name="fee_note" value="${escapeHtml(item.fee_note || "")}" /></div><label class="check"><input name="is_active" type="checkbox" ${item.is_active ? "checked" : ""} /> Show this course on the public site</label></div><div class="field"><label>Year-wise fee breakdown</label><div id="fee-rows">${rows}</div><button class="button secondary small" id="add-fee" type="button">+ Add fee year</button></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="course-form">Save course</button>`);
  el.querySelector("#add-fee").onclick = () => el.querySelector("#fee-rows").insertAdjacentHTML("beforeend", feeRow("", ""));
  el.querySelector("#fee-rows").addEventListener("click", (event) => event.target.closest("[data-remove-fee]")?.parentElement.remove());
  el.querySelector("#course-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); const fee_breakup = [...el.querySelectorAll(".fee-row")].map((row) => ({ label: row.querySelector("[name=fee_label]").value.trim(), amount_inr: Number(row.querySelector("[name=fee_amount]").value) })).filter((row) => row.label); try { await api(`/admin/courses/${item.code}`, { method: "PATCH", body: { name: f.get("name"), duration_text: f.get("duration_text"), total_fee_inr: Number(f.get("total_fee_inr")), display_order: Number(f.get("display_order")), summary: f.get("summary") || null, eligibility: f.get("eligibility") || null, fee_note: f.get("fee_note") || null, fee_breakup, is_active: f.get("is_active") === "on" } }); el.remove(); notice("Course saved."); renderPage(); } catch (error) { problem(error); } };
}
const feeRow = (label, amount) => `<div class="fee-row"><input name="fee_label" placeholder="Year 1" value="${escapeHtml(label)}" /><input name="fee_amount" type="number" min="0" placeholder="Amount" value="${escapeHtml(amount)}" /><button type="button" class="button secondary small" data-remove-fee>×</button></div>`;

async function batches(target) {
  const [items, courses] = await Promise.all([api("/admin/batches"), api("/admin/courses")]); state.cache.courses = courses;
  target.innerHTML = `${title("Batches", "Schedule online and offline batches for each course.", `<button class="button" id="add-batch">+ Add batch</button>`)}<div class="toolbar"><input class="search" placeholder="Search course, timing or mode" data-filter /></div>${panel("Batch timeline", table(["Course", "Dates", "Timings", "Mode", "Status", ""], items.map((item) => `<tr data-search="${escapeHtml(`${item.course_name} ${item.timings} ${item.mode}`)}"><td><strong>${escapeHtml(item.course_name)}</strong></td><td>${date(item.start_date)}<br><small>to ${date(item.end_date)}</small></td><td>${escapeHtml(item.timings)}</td><td>${escapeHtml(item.mode)}</td><td>${batchPhase(item)}</td><td><button class="button secondary small" data-edit-batch="${item.id}">Edit</button> <button class="button danger small" data-delete-batch="${item.id}">Delete</button></td></tr>`).join("")))}`;
  filterTable(target); target.querySelector("#add-batch").onclick = () => batchModal(null, courses);
  target.querySelectorAll("[data-edit-batch]").forEach((button) => button.onclick = () => batchModal(items.find((x) => x.id === button.dataset.editBatch), courses));
  target.querySelectorAll("[data-delete-batch]").forEach((button) => button.onclick = async () => { if (await confirmAction("Delete batch", "This batch will no longer appear on the website.")) { try { await api(`/admin/batches/${button.dataset.deleteBatch}`, { method: "DELETE" }); notice("Batch deleted."); renderPage(); } catch (error) { problem(error); } } });
}

function batchModal(item, courses) {
  const create = !item; const el = modal(create ? "Add batch" : "Edit batch", `<form id="batch-form"><div class="form-grid">${create ? `<div class="field full"><label>Course</label><select name="course_code">${courses.map((course) => `<option value="${course.code}">${escapeHtml(course.name)}</option>`).join("")}</select></div>` : `<div class="field full"><label>Course</label><input disabled value="${escapeHtml(item.course_name)}" /></div>`}<div class="field"><label>Start date</label><input name="start_date" type="date" required value="${item?.start_date || ""}" /></div><div class="field"><label>End date</label><input name="end_date" type="date" required value="${item?.end_date || ""}" /></div><div class="field"><label>Batch timing</label><input name="timings" required value="${escapeHtml(item?.timings || "")}" placeholder="10:00 AM - 1:00 PM" /></div><div class="field"><label>Mode</label><select name="mode"><option value="offline" ${item?.mode === "offline" ? "selected" : ""}>Offline</option><option value="online" ${item?.mode === "online" ? "selected" : ""}>Online</option></select></div><label class="check"><input name="is_active" type="checkbox" ${item?.is_active !== false ? "checked" : ""}/> Active on website</label></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="batch-form">${create ? "Add batch" : "Save changes"}</button>`);
  el.querySelector("#batch-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); const payload = { start_date: f.get("start_date"), end_date: f.get("end_date"), timings: f.get("timings"), mode: f.get("mode"), is_active: f.get("is_active") === "on" }; if (create) payload.course_code = f.get("course_code"); try { await api(create ? "/admin/batches" : `/admin/batches/${item.id}`, { method: create ? "POST" : "PATCH", body: payload }); el.remove(); notice(create ? "Batch added." : "Batch updated."); renderPage(); } catch (error) { problem(error); } };
}

async function brochures(target) {
  target.innerHTML = unavailablePage("Brochures", "The verified PlanetFiance schema does not yet contain brochure metadata. This page is disabled until that schema is approved and migrated.");
}

async function banners(target) {
  const [items, courses] = await Promise.all([api("/admin/banners"), api("/admin/courses")]);
  target.innerHTML = `${title("Banners", "Control the website hero slider and optional brochure call-to-actions.", `<button class="button" id="add-banner">+ Add banner</button>`)}<div class="toolbar"><input class="search" placeholder="Search banners" data-filter /></div>${panel("Website banners", table(["Image", "Title", "Brochure button", "Order", "Status", ""], items.map((item) => `<tr data-search="${escapeHtml(item.title)}"><td><img class="preview" src="${escapeHtml(item.thumb_url)}" alt="" /></td><td><strong>${escapeHtml(item.title)}</strong></td><td>${item.course_code || "—"}</td><td>${item.display_order}</td><td>${status(item.is_active)}</td><td><button class="button secondary small" data-edit-banner="${item.id}">Edit</button> <button class="button secondary small" data-image-banner="${item.id}">Image</button> <button class="button danger small" data-delete-banner="${item.id}">Delete</button></td></tr>`).join("")))}`;
  filterTable(target); target.querySelector("#add-banner").onclick = () => bannerModal(null, courses); target.querySelectorAll("[data-edit-banner]").forEach((button) => button.onclick = () => bannerModal(items.find((x) => x.id === button.dataset.editBanner), courses)); target.querySelectorAll("[data-image-banner]").forEach((button) => button.onclick = () => imageReplaceModal("banner", button.dataset.imageBanner)); target.querySelectorAll("[data-delete-banner]").forEach((button) => button.onclick = async () => { if (await confirmAction("Delete banner", "The banner image will be removed from storage and the website.")) { try { await api(`/admin/banners/${button.dataset.deleteBanner}`, { method: "DELETE" }); notice("Banner deleted."); renderPage(); } catch (error) { problem(error); } } });
}

function bannerModal(item, courses) {
  const create = !item; const el = modal(create ? "Add banner" : "Edit banner", `<form id="banner-form"><div class="form-grid"><div class="field full"><label>Title</label><input required name="title" value="${escapeHtml(item?.title || "")}" /></div><div class="field"><label>Optional brochure button</label><select name="course_code"><option value="">No brochure button</option>${courses.map((c) => `<option value="${c.code}" ${item?.course_code === c.code ? "selected" : ""}>${escapeHtml(c.name)}</option>`).join("")}</select></div><div class="field"><label>Display order</label><input type="number" min="0" name="display_order" value="${item?.display_order || 0}" /></div><label class="check"><input type="checkbox" name="is_active" ${item?.is_active !== false ? "checked" : ""}/> Show on website</label>${create ? `<div class="field full"><label>Banner image</label><input required name="image" accept="image/jpeg,image/png,image/webp" type="file" /></div>` : ""}</div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="banner-form">${create ? "Upload banner" : "Save banner"}</button>`);
  el.querySelector("#banner-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); const payload = { title: f.get("title"), course_code: f.get("course_code") || null, display_order: Number(f.get("display_order")), is_active: f.get("is_active") === "on" }; try { if (create) { const data = new FormData(); Object.entries(payload).forEach(([k, v]) => data.append(k, v === null ? "" : v)); data.append("image", f.get("image")); await api("/admin/banners/", { method: "POST", body: data, form: true }); } else await api(`/admin/banners/${item.id}`, { method: "PATCH", body: payload }); el.remove(); notice(create ? "Banner uploaded." : "Banner saved."); renderPage(); } catch (error) { problem(error); } };
}

async function announcements(target) {
  const items = await api("/admin/announcements");
  target.innerHTML = `${title("Announcements", "Schedule prominent website notices, links and visibility.", `<button class="button" id="add-announcement">+ Add announcement</button>`)}<div class="toolbar"><input class="search" placeholder="Search announcements" data-filter /></div>${panel("Announcement strip", table(["Message", "Schedule", "Order", "Status", ""], items.map((item) => `<tr data-search="${escapeHtml(item.message)}"><td><strong>${escapeHtml(item.message)}</strong>${item.link_url ? `<br><small>${escapeHtml(item.link_url)}</small>` : ""}</td><td>${date(item.starts_at)} — ${date(item.ends_at)}</td><td>${item.display_order}</td><td>${status(item.is_active)}</td><td><button class="button secondary small" data-edit-announcement="${item.id}">Edit</button> <button class="button danger small" data-delete-announcement="${item.id}">Delete</button></td></tr>`).join("")))}`;
  filterTable(target); target.querySelector("#add-announcement").onclick = () => announcementModal(null); target.querySelectorAll("[data-edit-announcement]").forEach((button) => button.onclick = () => announcementModal(items.find((x) => x.id === button.dataset.editAnnouncement))); target.querySelectorAll("[data-delete-announcement]").forEach((button) => button.onclick = async () => { if (await confirmAction("Delete announcement", "This notice will be permanently removed.")) { try { await api(`/admin/announcements/${button.dataset.deleteAnnouncement}`, { method: "DELETE" }); notice("Announcement deleted."); renderPage(); } catch (error) { problem(error); } } });
}

function announcementModal(item) {
  const create = !item; const el = modal(create ? "Add announcement" : "Edit announcement", `<form id="announcement-form"><div class="form-grid"><div class="field full"><label>Message</label><textarea required name="message">${escapeHtml(item?.message || "")}</textarea></div><div class="field full"><label>Optional link</label><input type="url" name="link_url" value="${escapeHtml(item?.link_url || "")}" /></div><div class="field"><label>Show from</label><input type="datetime-local" name="starts_at" value="${datetimeLocal(item?.starts_at)}" /></div><div class="field"><label>Show until</label><input type="datetime-local" name="ends_at" value="${datetimeLocal(item?.ends_at)}" /></div><div class="field"><label>Display order</label><input type="number" min="0" name="display_order" value="${item?.display_order || 0}" /></div><label class="check"><input type="checkbox" name="is_active" ${item?.is_active !== false ? "checked" : ""}/> Show on website</label></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="announcement-form">Save announcement</button>`);
  el.querySelector("#announcement-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); const body = { message: f.get("message"), link_url: f.get("link_url") || null, starts_at: f.get("starts_at") ? new Date(f.get("starts_at")).toISOString() : null, ends_at: f.get("ends_at") ? new Date(f.get("ends_at")).toISOString() : null, display_order: Number(f.get("display_order")), is_active: f.get("is_active") === "on" }; try { await api(create ? "/admin/announcements" : `/admin/announcements/${item.id}`, { method: create ? "POST" : "PUT", body }); el.remove(); notice("Announcement saved."); renderPage(); } catch (error) { problem(error); } };
}

async function gallery(target) {
  target.innerHTML = unavailablePage("Gallery", "The verified PlanetFiance schema does not yet contain gallery image metadata. This page is disabled until that schema is approved and migrated.");
}

async function videos(target) {
  const items = await api("/admin/videos");
  target.innerHTML = `${title("Videos", "Manage YouTube, YouTube Shorts and Instagram Reel links.", `<button class="button" id="add-video">+ Add video</button>`)}<div class="toolbar"><input class="search" placeholder="Search videos" data-filter /></div>${panel("Video library", table(["Video", "Platform", "Preview", "Order", "Status", ""], items.map((item) => `<tr data-search="${escapeHtml(`${item.title} ${item.platform}`)}"><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.url)}</small></td><td>${escapeHtml(item.platform.replaceAll("_", " "))}</td><td><a class="button secondary small" target="_blank" href="${escapeHtml(item.embed_url)}">Preview</a></td><td>${item.display_order}</td><td>${status(item.is_active)}</td><td><button class="button secondary small" data-edit-video="${item.id}">Edit</button> <button class="button danger small" data-delete-video="${item.id}">Delete</button></td></tr>`).join("")))}`;
  filterTable(target); target.querySelector("#add-video").onclick = () => videoModal(null); target.querySelectorAll("[data-edit-video]").forEach((button) => button.onclick = () => videoModal(items.find((x) => x.id === button.dataset.editVideo))); target.querySelectorAll("[data-delete-video]").forEach((button) => button.onclick = async () => { if (await confirmAction("Delete video", "This embedded video will be removed from the website.")) { try { await api(`/admin/videos/${button.dataset.deleteVideo}`, { method: "DELETE" }); notice("Video deleted."); renderPage(); } catch (error) { problem(error); } } });
}

function videoModal(item) {
  const create = !item; const el = modal(create ? "Add video" : "Edit video", `<form id="video-form"><div class="form-grid"><div class="field full"><label>Title</label><input required name="title" value="${escapeHtml(item?.title || "")}" /></div><div class="field full"><label>YouTube, Shorts or Instagram Reel URL</label><input required type="url" name="url" value="${escapeHtml(item?.url || "")}" /></div><div class="field"><label>Display order</label><input name="display_order" type="number" min="0" value="${item?.display_order || 0}" /></div><label class="check"><input name="is_active" type="checkbox" ${item?.is_active !== false ? "checked" : ""}/> Show on website</label></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="video-form">Save video</button>`);
  el.querySelector("#video-form").onsubmit = async (event) => { event.preventDefault(); const f = new FormData(event.currentTarget); try { await api(create ? "/admin/videos" : `/admin/videos/${item.id}`, { method: create ? "POST" : "PUT", body: { title: f.get("title"), url: f.get("url"), display_order: Number(f.get("display_order")), is_active: f.get("is_active") === "on" } }); el.remove(); notice("Video saved."); renderPage(); } catch (error) { problem(error); } };
}

async function exam(target) {
  const sets = await api("/admin/exam/sets");
  target.innerHTML = `${title("Mock exam", "Validate, preview and manage the three existing question-set slots.", `<a class="button secondary" href="/api/v1/admin/exam/template">Download Excel template</a>`)}${panel("Question sets", `<div class="grid cards">${sets.map((item) => `<article class="card metric"><small>Set ${item.slot}</small><strong>${item.exam_set ? item.exam_set.question_count : 0}</strong><p>${item.exam_set ? escapeHtml(item.exam_set.name) : "No file uploaded"}</p><div class="actions"><button class="button secondary small" data-exam-upload="${item.slot}">${item.exam_set ? "Replace" : "Upload"}</button>${item.exam_set ? `<button class="button danger small" data-exam-delete="${item.slot}">Remove</button>` : ""}</div></article>`).join("")}</div>`)}`;
  target.querySelectorAll("[data-exam-upload]").forEach((button) => button.onclick = () => examUploadModal(Number(button.dataset.examUpload), sets.find((x) => x.slot === Number(button.dataset.examUpload)))); target.querySelectorAll("[data-exam-delete]").forEach((button) => button.onclick = () => deleteExamSet(Number(button.dataset.examDelete)));
}

function examUploadModal(slot, existing) {
  const el = modal(`Question set ${slot}`, `<form id="exam-form"><div class="field"><label>Set name</label><input name="name" value="${escapeHtml(existing?.exam_set?.name || `Set ${slot}`)}" /></div><div class="file-drop"><label>Excel question file (.xlsx)<input required name="file" accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" type="file" /></label><p id="exam-validation">Select a file, then validate before importing.</p></div><div class="actions"><button class="button secondary" id="validate-exam" type="button">Validate file</button></div><div id="validation-report"></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" id="import-exam" form="exam-form" disabled>${existing?.exam_set ? "Replace set" : "Import set"}</button>`);
  let validated = false;
  el.querySelector("#validate-exam").onclick = async () => {
    const input = el.querySelector("input[type=file]");
    if (!input.files[0]) return notice("Choose an Excel file first.", true);
    const data = new FormData(); data.append("file", input.files[0]);
    try {
      const preview = await api("/admin/exam/sets/preview", { method: "POST", body: data, form: true });
      const report = preview.report; validated = report.ok; el.querySelector("#import-exam").disabled = !validated;
      const issues = [...report.errors, ...report.warnings];
      const questionPreview = preview.questions.length ? `<h3>Question preview</h3><ol>${preview.questions.map((q) => `<li><strong>${escapeHtml(`${q.section} · ${q.subsection}`)}</strong><br>${escapeHtml(q.content.map((part) => part.text || "").join(" "))}<br><small>${q.options.map(escapeHtml).join(" · ")}</small></li>`).join("")}</ol>` : "";
      el.querySelector("#validation-report").innerHTML = `<div class="detail-list" style="margin-top:14px"><div><span>Questions found</span><strong>${report.question_count}</strong></div><div><span>Passages found</span><strong>${report.passage_count}</strong></div><div><span>Validation</span>${report.ok ? status(true, "Ready to import") : `<span class="status warning">Fix issues first</span>`}</div></div>${issues.length ? `<ul>${issues.slice(0, 12).map((issue) => `<li>${escapeHtml(`${issue.sheet}${issue.row ? ` row ${issue.row}` : ""}: ${issue.message}`)}</li>`).join("")}</ul>` : ""}${questionPreview}`;
    } catch (error) { problem(error); }
  };
  el.querySelector("#exam-form").onsubmit = async (event) => { event.preventDefault(); if (!validated) return notice("Validate the file successfully before importing.", true); const f = new FormData(event.currentTarget); try { if (existing?.exam_set && !(await confirmAction("Replace question set", "The current set will be deleted before this validated file is imported. Active student attempts using it will expire.", "Replace"))) return; if (existing?.exam_set) await api(`/admin/exam/sets/${slot}`, { method: "DELETE" }); await api(`/admin/exam/sets/${slot}`, { method: "POST", body: f, form: true }); el.remove(); notice("Question set imported."); renderPage(); } catch (error) { problem(error); } };
}

async function deleteExamSet(slot) { if (await confirmAction("Remove question set", "Students will not be assigned this set after it is removed.")) { try { await api(`/admin/exam/sets/${slot}`, { method: "DELETE" }); notice("Question set removed."); renderPage(); } catch (error) { problem(error); } } }

async function leads(target) {
  target.innerHTML = unavailablePage("Lead delivery", "Google Sheets retry status requires the pending_sheet_rows table, which is not in the verified PlanetFiance schema. Existing direct Google Sheets delivery remains unchanged.");
}

const unavailablePage = (heading, message) => `${title(heading, "Unavailable until its database schema is implemented.")}<section class="panel"><div class="panel-body"><p style="color:var(--muted);margin:0">${escapeHtml(message)}</p></div></section>`;

function imageReplaceModal(kind, id) {
  const el = modal("Replace banner image", `<form id="replace-image"><div class="field"><label>New JPEG, PNG or WebP image</label><input name="image" required accept="image/jpeg,image/png,image/webp" type="file" /></div></form>`, `<button class="button secondary" data-close-modal>Cancel</button><button class="button" form="replace-image">Replace image</button>`);
  el.querySelector("#replace-image").onsubmit = async (event) => { event.preventDefault(); try { await api(`/admin/${kind}s/${id}/image`, { method: "PUT", body: new FormData(event.currentTarget), form: true }); el.remove(); notice("Image replaced."); renderPage(); } catch (error) { problem(error); } };
}

function filterTable(target) { const input = target.querySelector("[data-filter]"); if (!input) return; input.oninput = () => target.querySelectorAll("tr[data-search]").forEach((row) => { row.hidden = !row.dataset.search.toLowerCase().includes(input.value.toLowerCase()); }); }
function bindPageLinks(target) { target.querySelectorAll("[data-page-link]").forEach((button) => button.onclick = () => { state.page = button.dataset.pageLink; shell(); renderPage(); }); }

root.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="/api/v1/admin/"]');
  if (!link) return;
  event.preventDefault();
  secureFile(link.getAttribute("href").replace("/api/v1", ""), "download");
});

async function boot() {
  if (localVisualPreview) {
    state.visualPreview = true;
    state.user = { email: "local-preview@planetfiance.invalid" };
    shell();
    renderPage();
    return;
  }
  const config = window.__FIREBASE_CONFIG__;
  if (!config?.apiKey || !config?.authDomain || !config?.appId) { loginScreen("Firebase web configuration is missing. Set FIREBASE_WEB_* values for this environment before signing in."); return; }
  state.auth = getAuth(initializeApp(config));
  onAuthStateChanged(state.auth, async (user) => {
    state.user = user;
    if (!user) { loginScreen(); return; }
    try {
      await user.getIdToken(true);
      await api("/admin/me");
      shell(); renderPage();
    } catch (error) {
      problem(error);
      await signOut(state.auth);
    }
  });
}
boot();
