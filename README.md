# InOut-register

InOut-register is a small Flask application for tracking in/out register data. It uses SQLite for local storage and a modular blueprint-based structure for public, auth, admin and user pages.

## Project Overview

The application uses an application factory and Flask blueprints. Key entry points and features:

- `run.py` — start the app using the project entry point
- `CampusTrack/` — main application package (contains `auth`, `admin`, `main`, `user`, `superuser` blueprints)
- SQLite used for local development; no external services required by default

## Prerequisites

- Python 3.12 or newer
- `pip`
- A terminal or command prompt

## Create the Virtual Environment

Create a local virtual environment named `.venv` in the project root. Example (Linux/macOS):

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows (PowerShell):

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
```

## Install Dependencies

After activating the virtual environment, install the exact dependency set from `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Environment Variables

No environment variables are required for the current codebase.

If you later add configuration, store local values in a `.env` file and keep it out of version control.

## Run the Project

With the virtual environment activated, start the app from the project root:

```bash
python run.py
```

The app will start on the default Flask development server, usually at `http://127.0.0.1:5000`.

## Create the Database

This project uses SQLite. To create the database and tables, open a Python shell from the project root after activating the virtualenv and run:

```bash
python
```

Then inside the Python REPL:

```python
from CampusTrack import create_app
from CampusTrack.extensions import db
app = create_app()
with app.app_context():
    db.create_all()
```

This must run inside `app.app_context()` because SQLAlchemy needs an active Flask application context to access app configuration.

## Deactivate the Virtual Environment

When you are done, deactivate the environment with:

```bash
deactivate
```

## Project Structure

```text
.
InOut-register/
├── .venv/                   # Virtual environment folder (local, not committed)
├── instance/                # Instance folder for secret keys, local SQLite DBs (git-ignored)
├── CampusTrack/             # Main application package
│   ├── __init__.py          # Application Factory: defines create_app()
│   ├── extensions.py        # Shared extension instances (e.g., SQLAlchemy db = SQLAlchemy())
│   ├── models.py            # Shared database models
│   ├── auth/                # Auth blueprint (auth_bp)
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── main/                # Main site blueprint
│   ├── admin/               # Admin blueprint
│   ├── user/                # User blueprint
│   └── superuser/           # Superuser blueprint
├── .gitignore
├── README.md
├── requirements.txt
└── run.py
```
## System Architecture

<img width="1151" height="816" alt="Untitled Diagram drawio" src="/workspaces/InOut-register/CampusTrack/static/img/sa.png" />

## Troubleshooting

- If the app cannot import Flask or Flask-SQLAlchemy, make sure the virtual environment is activated before running it.
- If `python` still points to a global interpreter, confirm the shell prompt shows `.venv` and run `which python` to verify the active interpreter.
- If the port is already in use, stop the other process or run Flask on a different port.
- If `db.create_all()` fails, ensure you created an app instance via `create_app()` and run `db.create_all()` inside `with app.app_context():` as shown above.

## Notes

- The database is local SQLite, so no separate database server is required.
- The `.venv` directory and local database files are ignored by Git by default.