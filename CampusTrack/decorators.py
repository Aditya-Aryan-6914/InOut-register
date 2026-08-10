"""
Role-based access control for view functions.

Usage
-----
    from ..decorators import role_required
    from ..models import RoleEnum

    @admin_bp.route("/dashboard")
    @role_required(RoleEnum.ADMIN)
    def dashboard():
        ...

`role_required` already checks that the visitor is logged in — you do
NOT need to also stack Flask-Login's `@login_required` above it.
- Not logged in at all            -> redirected to the right login page
                                      (see extensions.unauthorized_handler)
- Logged in but wrong role        -> 403 Forbidden
- Logged in with an allowed role  -> view runs normally

Accepts one or more roles, as RoleEnum members or plain strings:
    @role_required(RoleEnum.ADMIN)
    @role_required(RoleEnum.ADMIN, RoleEnum.SUPERUSER)
    @role_required("admin", "superuser")
"""
from functools import wraps

from flask import abort
from flask_login import current_user

from .extensions import login_manager


def role_required(*roles):
    # Imported inside the function (not at module level) to avoid a
    # circular import between decorators.py and models.py.
    from .models import RoleEnum

    allowed = {r.value if isinstance(r, RoleEnum) else str(r) for r in roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            if current_user.role.value not in allowed:
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped_view

    return decorator
