"""
Shared Flask extension instances.

Import `db` and `login_manager` from here everywhere else in the app —
never create a second SQLAlchemy() or LoginManager() instance, or you'll
get two disconnected registries and confusing bugs.
"""
from flask import redirect, request, url_for
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

login_manager = LoginManager()
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "info"


@login_manager.unauthorized_handler
def unauthorized():
    """
    We have THREE separate login pages (admin/user/superuser), not one,
    so Flask-Login's usual single `login_view` doesn't fit. Instead,
    send an unauthenticated visitor to whichever login page matches the
    portal they were trying to reach, and remember where they were
    headed via `next` so they land back there after logging in.
    """
    if request.path.startswith("/admin"):
        target = "auth.admin_login"
    elif request.path.startswith("/superuser"):
        target = "auth.superuser_login"
    else:
        target = "auth.user_login"
    return redirect(url_for(target, next=request.path))
