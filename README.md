# InOut-register

InOut-register is a small Flask application for tracking in/out register data. It uses SQLite for local storage and a simple web UI for the public and admin pages.

## Project Overview

The application is a minimal Flask project with two routes:

- `/` for the main landing page
- `/admin` for the admin page

The current setup uses SQLite and does not require any external services or environment variables.

## Prerequisites

- Python 3.12 or newer
- `pip`
- A terminal or command prompt

## Create the Virtual Environment

Create a local virtual environment named `.venv` in the project root.

### Windows

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
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
python app.py
```

The app will start on the default Flask development server, usually at `http://127.0.0.1:5000`.

## Deactivate the Virtual Environment

When you are done, deactivate the environment with:

```bash
deactivate
```

## Project Structure

```text
.
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── instance/
└── templates/
	├── admin.html
	└── index.html
```

## Troubleshooting

- If the app cannot import Flask or Flask-SQLAlchemy, make sure the virtual environment is activated before running it.
- If `python` still points to a global interpreter, confirm the shell prompt shows `.venv` and run `which python` or `where python` to verify the active interpreter.
- If the port is already in use, stop the other process or run Flask on a different port.
- If SQLite data becomes corrupted during local testing, delete the local `inout.db` file and restart the app to recreate it.

## Notes

- The database is local SQLite, so no separate database server is required.
- The generated `.venv` directory and local database files are ignored by Git.