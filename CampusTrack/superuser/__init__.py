from flask import Blueprint

superuser_bp = Blueprint("superuser", __name__, url_prefix="/superuser")

from . import routes  # noqa: E402,F401
