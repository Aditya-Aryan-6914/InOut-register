"""
User portal routes — everything under /user/*.
"""
from flask import render_template
from flask_login import current_user

from . import user_bp
from ..decorators import role_required
from ..models import AttendanceLog, RoleEnum


@user_bp.route("/dashboard")
@role_required(RoleEnum.USER)
def dashboard():
    recent_logs = (
        current_user.attendance_logs.order_by(AttendanceLog.timestamp.desc()).limit(10).all()
    )
    return render_template(
        "user/dashboard.html",
        user=current_user,
        status=current_user.current_status,
        recent_logs=recent_logs,
    )


@user_bp.route("/scan")
@role_required(RoleEnum.USER)
def scan():
    # TODO: html5-qrcode camera view -> face capture -> geolocation ->
    # POST to a verification endpoint (the one place all three factors
    # from the CampusTrack plan meet). This route just renders the page.
    return render_template("user/scan.html")
