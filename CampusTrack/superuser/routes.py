"""
Superuser portal routes — everything under /superuser/*.
"""
from flask import render_template

from . import superuser_bp
from ..decorators import role_required
from ..models import Institute, RoleEnum


@superuser_bp.route("/dashboard")
@role_required(RoleEnum.SUPERUSER)
def dashboard():
    institutes = Institute.query.order_by(Institute.name).all()
    return render_template("superuser/dashboard.html", institutes=institutes)


@superuser_bp.route("/institutes/<int:institute_id>")
@role_required(RoleEnum.SUPERUSER)
def institute_detail(institute_id):
    institute = Institute.query.get_or_404(institute_id)
    return render_template(
        "superuser/institute_detail.html",
        institute=institute,
        users=institute.users.filter_by(role=RoleEnum.USER).all(),
    )
