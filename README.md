# InOut-register

InOut-register is a Flask-based campus attendance and in/out registration app. It now uses a package-based structure with blueprints for the main landing pages and authentication-related routes, backed by SQLite.

## Project Overview

The application currently provides:

- `/` for the main landing page
- `/admin` for the admin page
- `/admin/login` for the admin login view
- `/user/login` for the user login view

The project is organized as a proper Flask package so routes and app configuration are easier to extend.

## Prerequisites

- Python 3.12 or newer
- `pip`
- A terminal

## Create the Virtual Environment

Create a local virtual environment named `.venv` in the project root.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## Install Dependencies

After activating the virtual environment, install the dependencies from `requirements.txt`:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Run the Project

Start the app from the project root:

```bash
python run.py
```

The app will run on:

```text
http://127.0.0.1:5000/
```

## Run Tests

The project includes a small regression test suite for the routing setup:

```bash
pytest -q
```

If you are using the project virtual environment, run the command after activating it.

## Project Structure

```text
.
├── CampusTrack/
│   ├── __init__.py
│   ├── extensions.py
│   ├── models.py
│   ├── auth/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── main/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── static/
│   ├── templates/
│   └── instance/
├── tests/
├── run.py
├── requirements.txt
└── README.md
```

## Database Notes

The app uses SQLite by default. The database file is created locally as `inout.db` when the app starts.

## Deactivate the Virtual Environment

When you are done, deactivate the environment with:

```bash
deactivate
```

## Troubleshooting

- If Flask cannot be imported, make sure the virtual environment is activated.
- If `pytest` is not found, install dependencies in the active virtual environment first.
- If the app port is already in use, stop the conflicting process or run the app on another port.
- If you want a fresh local database, remove the generated `inout.db` file and restart the app.
