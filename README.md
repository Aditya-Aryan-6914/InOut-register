# CampusTrack (InOut-register)

CampusTrack is a Flask-based digital in/out attendance register for hostels,
classrooms, apartment complexes, or any place that currently tracks
attendance with a paper register. Instead of signing a sheet, a person
scans a QR code, has their face verified against their registered photo,
and has their GPS location checked against the checkpoint — all three
checks have to pass for a check-in/check-out to count as verified.

The project has three roles — **Superuser**, **Admin**, and **User** — that
share one login-and-role system, and it supports multiple independent
institutes (colleges, hostels, companies, etc.) on the same deployment.

---

## Table of contents

1. [What the app actually does](#what-the-app-actually-does)
2. [Tech stack](#tech-stack)
3. [Roles and authentication](#roles-and-authentication)
4. [Data model](#data-model)
5. [Feature walkthroughs](#feature-walkthroughs)
   - [Admin signup & institute creation](#admin-signup--institute-creation)
   - [Custom registration fields (drag-and-drop builder)](#custom-registration-fields-drag-and-drop-builder)
   - [Rooms & QR codes](#rooms--qr-codes)
   - [User registration & approval](#user-registration--approval)
   - [The scan flow: QR + face + geolocation](#the-scan-flow-qr--face--geolocation)
   - [Admin dashboard](#admin-dashboard)
   - [Superuser portal](#superuser-portal)
6. [Project structure](#project-structure)
7. [Setup & installation](#setup--installation)
8. [Creating the first superuser account](#creating-the-first-superuser-account)
9. [Running the app](#running-the-app)
10. [Running tests](#running-tests)
11. [Security notes & known limitations](#security-notes--known-limitations)
12. [Troubleshooting](#troubleshooting)

---

## What the app actually does

A typical flow looks like this:

1. Someone signs up as an **Admin** and, in the same step, creates their
   **Institute** (a college, hostel, company, etc.).
2. The Admin defines **custom registration fields** for their institute
   (e.g. "Room Number", "Roll Number", "Department") using a
   drag-and-drop form builder.
3. The Admin generates **Rooms** (checkpoints) — each one gets its own
   signed, unique **QR code**, and the Admin can set that room's GPS
   location and geofence radius.
4. A prospective **User** picks their institute, enters the institute's
   shared join password, fills in the custom fields, uploads a profile
   photo, and submits a **join request**.
5. The Admin reviews pending join requests and **approves or rejects**
   them. Approval turns the request into a real, logged-in-capable User
   account.
6. The User logs in and uses the **scan page**: they scan a Room's QR
   code, the camera captures their face, and the browser reports GPS
   coordinates. The server checks all three:
   - **QR** — was this a real, unforged CampusTrack QR code for a room in
     this user's own institute?
   - **Face** — does the captured photo match the user's registered
     profile photo (OpenCV LBPH face recognition)?
   - **Location** — is the user's GPS position within the room's geofence
     radius?
7. Every scan attempt is recorded as an `AttendanceLog` row — a
   **check-in** or **check-out**, whichever the user's last event implies
   is next. If all three checks pass, it counts toward the live "who's
   currently in" dashboard; if any check fails, the attempt is still
   logged (flagged) for the admin to review, rather than silently
   disappearing.
8. A platform-wide **Superuser** can see every institute, drill into any
   one of them, and suspend, reactivate, change the plan of, or
   permanently delete an institute.

---

## Tech stack

| Layer            | Choice                                           |
|-------------------|--------------------------------------------------|
| Web framework     | Flask 3.x, application-factory pattern           |
| ORM / database    | Flask-SQLAlchemy over SQLite (`instance/inout.db`) |
| Auth              | Flask-Login (session-based)                      |
| Password hashing  | Werkzeug's `generate_password_hash` / `check_password_hash` (salted) |
| QR codes          | `qrcode` (generation) + signed payloads via `itsdangerous` |
| Face verification | OpenCV (`opencv-contrib-python-headless`) — Haar cascade for face detection, LBPH for face matching |
| Geolocation       | Browser Geolocation API (client) + haversine distance (server) |
| Frontend          | Server-rendered Jinja templates, vanilla JS, SortableJS (drag-and-drop), html5-qrcode (QR scanning) |
| Image handling    | Pillow (re-encodes every uploaded photo before saving) |

No external services are required — everything runs locally against
SQLite, with no API keys or paid dependencies.

---

## Roles and authentication

CampusTrack uses **one `User` database table for all three roles**,
distinguished by a `role` column (`superuser` / `admin` / `user`), rather
than three separate tables. This keeps `Flask-Login`'s session/user-loader
logic in one place and makes role checks a single column comparison.

### Three separate login pages, not one

Because the three roles have entirely different dashboards and
permissions, there are three distinct login routes and templates:

| Role       | Login URL             | Lands on              |
|------------|------------------------|------------------------|
| Admin      | `/auth/admin/login`     | `/admin/dashboard`     |
| User       | `/auth/user/login`      | `/user/dashboard`      |
| Superuser  | `/auth/superuser/login` | `/superuser/dashboard` |

All three share one internal `_handle_login()` helper in
`CampusTrack/auth/routes.py` — the only thing that differs between them is
which `RoleEnum` to check the submitted email/password against, which
template to render, and where to redirect afterwards. This avoids three
near-identical copy-pasted route functions.

A login attempt is rejected if:
- the email/role combination doesn't exist, or the password is wrong
  (`"Invalid email or password."` — deliberately vague, so an attacker
  can't use the error message to enumerate which emails exist),
- the user's own account has been suspended,
- **or** the user's institute has been suspended by a superuser (this
  blocks Admins and Users of that institute from logging in — a
  superuser suspending an institute is meant to lock out everyone in it,
  not just stop new signups). Superusers have no institute, so this
  check never applies to them.

### Password storage

Every password — a User's login password, and an Institute's shared
"join password" — is stored as a salted hash via Werkzeug's
`generate_password_hash` / `check_password_hash`. Plaintext passwords are
never written to the database or logged.

### Role-based access control (`@role_required`)

Every protected route is guarded with a decorator from
`CampusTrack/decorators.py`:

```python
from ..decorators import role_required
from ..models import RoleEnum

@admin_bp.route("/dashboard")
@role_required(RoleEnum.ADMIN)
def dashboard():
    ...
```

`role_required` already includes the "must be logged in" check — you
don't stack Flask-Login's `@login_required` on top of it. Behavior:

- **Not logged in at all** → redirected to the correct login page for the
  section of the site being accessed (see below), with `?next=` set so
  the user lands back where they were headed after logging in.
- **Logged in, but wrong role** → HTTP 403 Forbidden.
- **Logged in with an allowed role** → the view runs normally.

It also accepts multiple roles for routes shared across roles, e.g.
`@role_required(RoleEnum.ADMIN, RoleEnum.SUPERUSER)`.

### Smart redirect on unauthorized access

Because there are three login pages, `Flask-Login`'s usual single
`login_view` setting doesn't fit. Instead,
`CampusTrack/extensions.py` defines a custom `unauthorized_handler` that
inspects the *path* the visitor was trying to reach and sends them to the
matching login page:

- `/admin/...` → admin login
- `/superuser/...` → superuser login
- anything else → user login

### Open-redirect protection on `?next=`

After logging in, the app redirects back to wherever the user was headed
(`?next=/admin/rooms`, for example). Before following that URL, the app
runs it through `_is_safe_next()`, which only allows plain relative paths
on the same site (must start with `/`, no scheme, no host). Without this
check, a crafted link like `/user/login?next=https://evil.example` could
send a freshly-logged-in user straight to an attacker's site.

### Institute-level data isolation (IDOR protection)

Admin routes never trust an ID in the URL at face value. Helpers like
`_get_own_room_or_404()` and `_get_own_join_request_or_404()` always
re-check that the requested row's `institute_id` matches the logged-in
admin's own institute before returning it — otherwise Admin A could
approve/reject/delete Admin B's data just by guessing an ID. A mismatch
returns a plain 404 (not a 403), so an admin can't even confirm that a
given ID belongs to *someone else's* institute.

Superuser routes deliberately have **no** such per-institute scoping —
seeing and managing every institute is the entire point of that role.
Every single superuser route is still gated behind
`@role_required(RoleEnum.SUPERUSER)`, with no exceptions.

### CSRF protection — current status

⚠️ **As of this writing, the application does not yet have CSRF
protection wired in.** Every POST route (login, signup, registration,
room actions, approve/reject, field-builder save, superuser actions, scan
verification) is currently open to cross-site request forgery. This is a
known, tracked gap — a complete implementation plan (using Flask-WTF's
`CSRFProtect`) exists and is ready to apply, but has not been merged as
of this README. If you're picking this project up, treat closing this
gap as a priority before deploying anywhere real users can reach it.

---

## Data model

All models live in `CampusTrack/models.py`. Key tables:

- **`Institute`** — one row per hostel/college/company. Holds the shared
  join password (hashed), status (`active` / `suspended`, set by a
  superuser), and plan (`free` / `subscribed`).
- **`User`** — one table for all three roles (see above). `institute_id`
  is `NULL` for superusers, and set for admins/users.
- **`CustomField`** — one row per field an admin has added to their
  institute's registration form (label, type, options for
  dropdown/checkbox, required flag, display order).
- **`JoinRequest`** — created when someone submits the registration form.
  Holds their chosen (hashed) password and custom-field answers as a JSON
  blob, pending admin approval. Never becomes a real login until
  approved.
- **`UserFieldValue`** — an approved user's normalized answer to one
  `CustomField`, copied over from their `JoinRequest` at approval time.
- **`Room`** — one checkpoint per QR code. Holds the signed `qr_token`,
  optional GPS coordinates, and geofence radius (default 100m).
- **`AttendanceLog`** — one row per scan attempt (check-in **or**
  check-out, not a paired record). Stores each verification factor
  (`qr_verified`, `face_verified`, `face_match_score`, `location_verified`)
  separately, plus an `is_flagged` flag and `flag_reason`, so a failed
  attempt is fully auditable rather than a black box.

"Is this person currently in?" is derived from **their most recent
verified `AttendanceLog` row**, not from a pair of matched
check-in/check-out records — simpler to reason about and harder to get
into an inconsistent state.

---

## Feature walkthroughs

### Admin signup & institute creation

`POST /auth/admin/signup` creates an `Institute` and its first `Admin`
user in a single form and a single DB transaction — an institute can't
exist without someone to administer it. Validation covers: institute
name/address, a duplicate-institute name warning (non-blocking — names
aren't required to be globally unique), admin name/email/password
confirmation, and an email-uniqueness check across the whole `User`
table.

### Custom registration fields (drag-and-drop builder)

`/admin/fields` renders the field builder (SortableJS, vendored locally —
no CDN dependency). The admin can add/remove/reorder fields of type
text, number, date, dropdown, checkbox, file, email, or phone.

Saving (`POST /admin/fields/save`) is a full-replace operation: the
frontend sends the entire ordered field list on every save, and the
server reconciles it against what's already in the database — fields
that still have a matching ID are updated in place, anything new is
inserted, and anything dropped from the payload is deleted (which
cascades to any `UserFieldValue` rows already answered against it). This
is deliberately atomic and easy to reason about, at the cost of not
supporting incremental per-field edits.

### Rooms & QR codes

`/admin/rooms` lets an admin generate a batch of rooms at once (up to
500 per institute) with a shared name prefix (e.g. "Room 1", "Room 2",
...). Each room gets a random `qr_token` (`secrets.token_urlsafe(12)`).

The QR **image** itself is generated on demand at
`/admin/rooms/<id>/qr.png` — it's never stored as a file. What's encoded
in the image isn't the room's database ID (which would let anyone forge
a QR by guessing sequential numbers); it's a payload **signed** with the
app's `SECRET_KEY` via `itsdangerous.URLSafeSerializer`
(`CampusTrack/qr_utils.py`):

```python
make_qr_payload(room)   # -> signed string, goes INTO the QR image
verify_qr_payload(s)    # -> {"i": institute_id, "r": room_id, "t": qr_token} or None
```

A scan endpoint can verify a scanned code came from CampusTrack without a
database round trip, and still separately checks the decoded room ID and
token against the live database (a valid signature only proves *we*
issued it — not that the room hasn't since been deleted or regenerated).

Admins can also rename a room, delete it (which cascades to its
`AttendanceLog` history, with a warning shown first), and set its GPS
location + geofence radius by standing at the room and using the
browser's own geolocation via an AJAX call to
`/admin/rooms/<id>/set-location`.

### User registration & approval

Registration is a three-step flow:

1. `GET /user/register` — shows a picker of all active institutes.
2. `POST /user/register/verify-institute` (AJAX) — the prospective user
   enters the institute's shared join password; on success, the server
   returns that institute's custom field definitions so the frontend can
   render step 2 without a page reload.
3. `POST /user/register` — the final multipart submission: name, email,
   phone, password, profile photo, and every custom field's answer.

The final submission **independently re-verifies** the institute password
from scratch — step 2's check is never trusted as sufficient on its own,
since it's a completely separate HTTP request that could be replayed or
skipped.

Validation covers: name length, email format + uniqueness (checked
against both existing `User` rows and other pending `JoinRequest` rows),
password length/confirmation match, a required profile photo, and every
custom field's required/valid-option constraints. Uploaded photos are
re-encoded through Pillow (not just accepted as-is), so a file that's
merely renamed to *look* like an image but isn't gets rejected instead of
silently stored.

Successful submission creates a `JoinRequest` — **not** a `User` — so no
login capability exists until an admin reviews it.

Admins approve/reject from their dashboard
(`POST /admin/requests/<id>/approve` or `/reject`). Approval copies the
join request's data into a real `User` row plus its `UserFieldValue`
rows; rejection records an optional reason. Both routes use the
institute-ownership guard described above, so an admin can never
approve/reject another institute's requests.

### The scan flow: QR + face + geolocation

This is the core feature. `POST /user/scan/verify` receives:
- `qr_payload` — the string decoded from the scanned QR image (client-side
  scanning via the vendored `html5-qrcode` library)
- `latitude` / `longitude` — from the browser's Geolocation API
- `photo` — a captured frame from the device camera

Server-side, in order:

1. **QR check** — decode and verify the signature (`verify_qr_payload`),
   confirm the room exists, is active, and belongs to the scanning user's
   own institute. Any failure here is a **hard reject with no log row at
   all** — this isn't "the checkpoint rejected you", it's "that wasn't a
   valid CampusTrack QR code".
2. **Cooldown check** — if the user's last logged event was less than 5
   seconds ago, reject with 429, to prevent an accidental double-fire of
   the camera from creating two log rows for one physical scan.
3. **Face check** (`CampusTrack/face_match.py`) — the captured photo is
   compared against the user's registered profile photo using OpenCV's
   LBPH (Local Binary Patterns Histograms) face recognizer. Both images
   go through Haar-cascade face detection and cropping first. A distance
   score ≤ 70 (empirically tuned) counts as a match.
4. **Location check** (`CampusTrack/geo_utils.py`) — if the room has GPS
   coordinates set, the haversine distance between the user's reported
   position and the room's position must be within the room's geofence
   radius. If the admin hasn't set the room's location yet, this check is
   **skipped and treated as passed** — a user isn't penalized for an
   admin's incomplete setup.
5. An `AttendanceLog` row is written **either way** — success or failure
   — recording each factor's result individually
   (`qr_verified`/`face_verified`/`face_match_score`/`location_verified`).
   Only fully-verified rows (`is_flagged = False`) count toward live
   in/out status and dashboard counts; flagged rows are preserved for
   admin review rather than silently discarded.
6. The event type (check-in vs. check-out) is inferred automatically: if
   the user's last verified event was a check-in, this one is a
   check-out, and vice versa.

> **Honesty note on the face-match method:** LBPH is a classical,
> texture-pattern-based algorithm — not deep-learning face embeddings
> (the kind `face_recognition`/dlib or a cloud face API would provide).
> It's a real, working recognizer, not a placeholder, but it's
> meaningfully more sensitive to lighting/pose/angle than an embeddings-based
> approach, and has **no liveness check** (a printed photo could fool it).
> It was chosen because dlib requires a from-source build that can take
> 15–30+ minutes and needs system build tools that may not be available in
> every dev/deployment environment, while LBPH installs in seconds via
> `opencv-contrib-python`. If this needs to be production-secure rather
> than architecturally-correct-for-a-project, `face_match.py` is the only
> file that would need to be swapped out — everything else in the check-in
> flow (QR signing, geofencing, logging, dashboards) stays the same.

### Admin dashboard

`/admin/dashboard` shows: active user count, currently-checked-in count,
today's check-in count, a per-room breakdown, the institute's custom
fields, and pending join requests to approve/reject. A companion
JSON endpoint, `/admin/dashboard/live-counts`, is polled roughly every 12
seconds by `admin_dashboard.js` to refresh the stat cards and per-room
table without a full page reload — scoped to the logged-in admin's own
institute like every other admin route.

### Superuser portal

`/superuser/dashboard` lists every institute on the platform, with a
search box that matches on institute name **or** an admin's name/email
(so a superuser can find "that one college" without remembering exactly
which field they know it by). It also shows platform-wide stats: total
institutes, total users, total admins, and today's check-ins summed
across every institute.

From `/superuser/institutes/<id>`, a superuser can:
- view every user, room, and custom field belonging to that institute,
- **suspend** it (blocks admin/user logins for that institute — see
  Authentication above),
- **reactivate** it,
- change its **plan** (`free` / `subscribed`),
- or **permanently delete** it — which cascades to every user, room,
  custom field, join request, attendance log, and field value it owns.
  Because this is irreversible, the confirmation requires typing the
  institute's exact name, not just a generic "are you sure?" dialog.

---

## Project structure

```text
InOut-register/
├── app.py                     # Entry point: app = create_app()
├── requirements.txt
├── conftest.py
├── tests/
│   └── test_app.py            # Minimal smoke-test suite
├── instance/                  # SQLite DB + secrets live here (git-ignored)
└── CampusTrack/                # Main application package
    ├── __init__.py             # Application factory: create_app()
    ├── extensions.py           # Shared db / login_manager instances, unauthorized handler
    ├── decorators.py           # @role_required
    ├── models.py                # All SQLAlchemy models
    ├── face_match.py           # OpenCV LBPH face verification
    ├── geo_utils.py             # Haversine distance for geofencing
    ├── qr_utils.py              # Signed QR payload helpers
    ├── uploads.py               # Photo/file upload validation & storage
    ├── main/                    # Public landing pages ("/", "/admin" info page)
    ├── auth/                    # Login (all 3 roles) + admin signup
    ├── admin/                   # Admin dashboard, field builder, rooms, approvals
    ├── user/                    # Registration, user dashboard, scan flow
    ├── superuser/                # Platform-wide institute management
    ├── templates/                # Jinja templates, mirrors the blueprint structure
    └── static/
        ├── css/
        ├── js/                   # Page-specific scripts + vendored SortableJS, html5-qrcode
        ├── img/
        └── uploads/               # User-uploaded photos/files (see security notes)
```

---

## Setup & installation

### Prerequisites

- Python 3.12 or newer
- `pip`

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Aditya-Aryan-6914/InOut-register.git
cd InOut-register
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> **OpenCV note:** `requirements.txt` pins exactly one OpenCV package —
> `opencv-contrib-python-headless==4.10.0.84`. That specific build was
> confirmed to include both `cv2.CascadeClassifier` (face detection) and
> `cv2.face.LBPHFaceRecognizer_create()` (face matching), which the app
> needs. **Do not additionally install `opencv-python-headless`** (or any
> other OpenCV variant) alongside it — both packages ship a top-level
> `cv2` folder, and having more than one installed corrupts the merged
> package (a common symptom: `ModuleNotFoundError: No module named
> 'cv2.typing'`). If you ever hit that error, uninstall every OpenCV
> variant and reinstall only the pinned one:
> ```bash
> pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python opencv-contrib-python-headless
> pip install opencv-contrib-python-headless==4.10.0.84
> ```

### 3. Environment variables

None are required to run the app locally — it falls back to a
development `SECRET_KEY` and a local SQLite file under `instance/`.

For anything beyond local development, set a real `SECRET_KEY` (used to
sign session cookies **and** every QR code payload):

```bash
export SECRET_KEY="a-long-random-value"   # Windows: set SECRET_KEY=...
```

### 4. Database setup

The database and all tables are created automatically the first time the
app starts (`db.create_all()` inside `create_app()`), so no separate
migration step is needed for a fresh setup. The SQLite file lands at
`instance/inout.db`.

---

## Creating the first superuser account

There is **intentionally no public signup page for the superuser role** —
a self-service form for the highest-privilege account would let anyone
who found it take over every institute, admin, and user on the platform.

Instead, use the Flask CLI command, which only runs from a trusted local
shell:

```bash
export FLASK_APP=app.py
flask create-superuser
```

You'll be prompted for a name, email, and password (hidden input, with
confirmation). Non-interactively:

```bash
flask create-superuser --name "Root Admin" --email root@example.com --password "a-strong-password"
```

The command rejects duplicate emails and passwords under 8 characters,
and creates the account with `role=superuser` and `institute_id=NULL`.
Log in afterward at `/auth/superuser/login`.

---

## Running the app

```bash
python app.py
```

By default this starts Flask's development server on
`http://0.0.0.0:5000` with debug mode on (`app.run(debug=True, ...)` in
`app.py`) — fine for local development, but debug mode should be off and
a production WSGI server (e.g. the `gunicorn` dependency already listed
in `requirements.txt`) should front the app in any real deployment.

---

## Running tests

```bash
pytest
```

The current suite (`tests/test_app.py`) is a minimal smoke test — it
confirms the app factory builds correctly and that the home page and
each login page render with a 200. It does **not** yet cover the actual
feature logic (registration, approval, the scan verification flow, or
superuser actions), so treat it as a starting point rather than full
coverage.

---

## Security notes & known limitations

Being upfront about the current state, not glossing over it:

- **CSRF protection is not yet implemented** (see [Authentication](#csrf-protection--current-status)
  above). Treat this as the top priority before any real deployment.
- **Uploaded files have no access control.** Profile photos and custom
  field file uploads are saved under `CampusTrack/static/uploads/` and
  served by Flask's static file handler. Filenames are random/unguessable
  (`uuid4().hex`), but anyone who obtains a URL can view the file with no
  authentication check. Before this goes anywhere real, move uploads
  outside `static/` and serve them through an authenticated route that
  checks the requester's role/institute first.
- **Face verification uses LBPH, not deep-learning embeddings**, and has
  no liveness detection — see the [scan flow](#the-scan-flow-qr--face--geolocation)
  section for the full reasoning. It's meaningfully weaker than a
  production biometric check and can be fooled by a printed photo.
- **No database migrations** — the schema is created with
  `db.create_all()`, which is fine until a schema change needs to happen
  without losing existing data. Introducing Flask-Migrate is recommended
  before that becomes a real constraint.
- **Institute join passwords are a shared secret**, hashed like a real
  password but inherently lower-security than per-user credentials
  (anyone who has it can start a registration). Treat it as a
  first-line gate to pair with admin approval, not a strong access
  control on its own.

---

## Troubleshooting

- **`ModuleNotFoundError: No module named 'cv2.typing'`** — you have more
  than one OpenCV package installed and they've corrupted each other's
  files. See the [OpenCV note](#2-install-dependencies) above for the
  fix.
- **App won't import Flask / Flask-SQLAlchemy** — make sure your virtual
  environment is activated (`source .venv/bin/activate`) before running
  anything.
- **Port already in use** — stop whatever else is bound to port 5000, or
  run with a different port: `flask run --port 5001` (with `FLASK_APP`
  set as above).
- **`db.create_all()` fails when run manually in a shell** — it must run
  inside `with app.app_context():`, since SQLAlchemy needs an active
  Flask application context to read the app's configuration.
- **Logged in, but every page 403s** — you're logged in with the wrong
  role for that section of the site (e.g. a User account visiting
  `/admin/...`). Log out and use the correct login page for that role.
- **QR scan says "isn't valid for your institute"** — the scanned code
  belongs to a room in a different institute than your account, or the
  room's QR was regenerated since the code was printed/saved.