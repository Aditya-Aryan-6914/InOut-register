"""
User portal routes — everything under /user/*.
"""
import re

from flask import flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from . import user_bp
from ..decorators import role_required
from ..extensions import db
from ..models import (
    AttendanceLog, CustomField, FieldTypeEnum, Institute, InstituteStatusEnum,
    JoinRequest, RequestStatusEnum, RoleEnum, User,
)
from ..uploads import UploadError, save_generic_file, save_photo_upload

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# =================================================================
# Registration — three steps:
#   1. GET  /user/register                 -> institute picker page
#   2. POST /user/register/verify-institute -> AJAX: check institute
#      password, return that institute's custom field definitions
#   3. POST /user/register                 -> final submission,
#      creates a JoinRequest (not a User — an admin must approve first)
# =================================================================

@user_bp.route("/register", methods=["GET"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("user.dashboard"))

    institutes = (
        Institute.query.filter_by(status=InstituteStatusEnum.ACTIVE)
        .order_by(Institute.name)
        .all()
    )
    return render_template("user/register.html", institutes=institutes)


@user_bp.route("/register/verify-institute", methods=["POST"])
def verify_institute():
    if current_user.is_authenticated:
        return jsonify({"error": "You're already logged in."}), 400

    payload = request.get_json(silent=True) or {}
    institute_id = payload.get("institute_id")
    password = payload.get("institute_password", "")

    institute = Institute.query.get(institute_id) if institute_id else None
    if institute is None or institute.status != InstituteStatusEnum.ACTIVE:
        return jsonify({"error": "Select a valid institute."}), 400
    if not institute.check_join_password(password):
        return jsonify({"error": "Incorrect institute password."}), 401

    fields = institute.custom_fields.order_by(CustomField.order).all()
    return jsonify({
        "success": True,
        "institute_id": institute.id,
        "fields": [
            {
                "id": f.id,
                "label": f.label,
                "field_type": f.field_type.value,
                "is_required": f.is_required,
                "options": f.options,
            }
            for f in fields
        ],
    })


@user_bp.route("/register", methods=["POST"])
def submit_registration():
    if current_user.is_authenticated:
        return redirect(url_for("user.dashboard"))

    institute_id = request.form.get("institute_id", type=int)
    institute_password = request.form.get("institute_password", "")
    institute = Institute.query.get(institute_id) if institute_id else None

    # Re-verify from scratch — never trust that step 2 already checked
    # this, since this is a completely separate HTTP request.
    if institute is None or institute.status != InstituteStatusEnum.ACTIVE:
        flash("Select a valid institute.", "error")
        return redirect(url_for("user.register"))
    if not institute.check_join_password(institute_password):
        flash("Incorrect institute password. Please start over.", "error")
        return redirect(url_for("user.register"))

    baseline = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip().lower(),
        "phone": request.form.get("phone", "").strip(),
    }
    password = request.form.get("password", "")
    password_confirm = request.form.get("password_confirm", "")
    photo = request.files.get("photo")

    custom_fields = institute.custom_fields.order_by(CustomField.order).all()

    errors = _validate_registration(baseline, password, password_confirm, photo, custom_fields)
    if errors:
        for error in errors:
            flash(error, "error")
        return _reopen_registration_form(institute, custom_fields, baseline)

    try:
        photo_path = save_photo_upload(photo)
        field_responses = _save_field_responses(custom_fields)
    except UploadError as exc:
        flash(str(exc), "error")
        return _reopen_registration_form(institute, custom_fields, baseline)

    join_request = JoinRequest(
        institute_id=institute.id,
        name=baseline["name"],
        email=baseline["email"],
        phone=baseline["phone"] or None,
        photo_path=photo_path,
        field_responses=field_responses,
    )
    join_request.set_password(password)
    db.session.add(join_request)
    db.session.commit()

    return render_template("user/register_pending.html", institute=institute)


def _reopen_registration_form(institute: Institute, custom_fields: list, baseline: dict):
    """
    Re-renders the registration page with step 2 already open for the
    given institute — used when the final submission fails validation,
    so the user doesn't have to re-enter the institute password and
    start over from step 1.
    """
    return render_template(
        "user/register.html",
        institutes=Institute.query.filter_by(status=InstituteStatusEnum.ACTIVE).order_by(Institute.name).all(),
        reopen_institute=institute,
        institute_fields=custom_fields,
        form=baseline,
    )


def _validate_registration(baseline: dict, password: str, password_confirm: str,
                            photo, custom_fields: list) -> list[str]:
    errors = []

    if len(baseline["name"]) < 2:
        errors.append("Enter your full name.")

    if not EMAIL_RE.match(baseline["email"]):
        errors.append("Enter a valid email address.")
    elif User.query.filter_by(email=baseline["email"]).first():
        errors.append("An account with this email already exists. Try logging in instead.")
    elif JoinRequest.query.filter_by(email=baseline["email"], status=RequestStatusEnum.PENDING).first():
        errors.append("A registration request with this email is already pending review.")

    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif password != password_confirm:
        errors.append("Passwords don't match.")

    if not photo or not photo.filename:
        errors.append("A profile photo is required.")

    for field in custom_fields:
        value = request.form.get(f"field_{field.id}", "").strip()
        selected = request.form.getlist(f"field_{field.id}")

        if field.field_type == FieldTypeEnum.CHECKBOX:
            if field.is_required and not selected:
                errors.append(f"'{field.label}' is required.")
            elif selected and not set(selected).issubset(set(field.options or [])):
                errors.append(f"'{field.label}' has an invalid selection.")
        elif field.field_type == FieldTypeEnum.DROPDOWN:
            if field.is_required and not value:
                errors.append(f"'{field.label}' is required.")
            elif value and field.options and value not in field.options:
                errors.append(f"'{field.label}' has an invalid selection.")
        elif field.field_type == FieldTypeEnum.FILE:
            uploaded = request.files.get(f"field_{field.id}")
            if field.is_required and (not uploaded or not uploaded.filename):
                errors.append(f"'{field.label}' is required.")
        else:
            if field.is_required and not value:
                errors.append(f"'{field.label}' is required.")

    return errors


def _save_field_responses(custom_fields: list) -> dict:
    """
    Reads each custom field's submitted value from the current request
    and returns {field_id_str: value_str}, ready to store on
    JoinRequest.field_responses. Assumes _validate_registration already
    confirmed everything required is present and valid.
    """
    responses = {}
    for field in custom_fields:
        if field.field_type == FieldTypeEnum.CHECKBOX:
            selected = request.form.getlist(f"field_{field.id}")
            if selected:
                responses[str(field.id)] = ",".join(selected)
        elif field.field_type == FieldTypeEnum.FILE:
            uploaded = request.files.get(f"field_{field.id}")
            if uploaded and uploaded.filename:
                responses[str(field.id)] = save_generic_file(uploaded)
        else:
            value = request.form.get(f"field_{field.id}", "").strip()
            if value:
                responses[str(field.id)] = value
    return responses


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
