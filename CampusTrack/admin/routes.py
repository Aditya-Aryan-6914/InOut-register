"""
Admin portal routes — everything under /admin/*.

Note: your existing bare "/admin" route (the public admin landing page,
per your README) is untouched — it presumably lives in the `main`
blueprint. Everything here sits one level deeper (/admin/dashboard,
/admin/fields, ...) so there's no collision.

These are intentionally thin for now — just enough to prove
`role_required` works end-to-end. Swap the TODOs for the real
drag-and-drop field builder / room+QR generation logic we planned
when you're ready to build those out.
"""
from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from . import admin_bp
from ..decorators import role_required
from ..extensions import db
from ..models import JoinRequest, RequestStatusEnum, RoleEnum, User, UserFieldValue


@admin_bp.route("/dashboard")
@role_required(RoleEnum.ADMIN)
def dashboard():
    institute = current_user.institute
    pending_requests = institute.join_requests.filter_by(
        status=RequestStatusEnum.PENDING
    ).all()

    return render_template(
        "admin/dashboard.html",
        institute=institute,
        active_users=institute.active_user_count,
        pending_requests=pending_requests,
        rooms=institute.rooms.all(),
    )


@admin_bp.route("/fields")
@role_required(RoleEnum.ADMIN)
def fields():
    # TODO: drag-and-drop field builder (SortableJS field bank + canvas)
    institute = current_user.institute
    return render_template("admin/fields.html", institute=institute,
                            custom_fields=institute.custom_fields.all())


@admin_bp.route("/rooms")
@role_required(RoleEnum.ADMIN)
def rooms():
    # TODO: "how many rooms?" form + bulk QR generation
    institute = current_user.institute
    return render_template("admin/rooms.html", institute=institute,
                            rooms=institute.rooms.all())


@admin_bp.route("/requests/<int:request_id>/approve", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def approve_request(request_id):
    join_request = _get_own_join_request_or_404(request_id)

    new_user = User(
        role=RoleEnum.USER,
        institute_id=join_request.institute_id,
        name=join_request.name,
        email=join_request.email,
        phone=join_request.phone,
        password_hash=join_request.password_hash,
        photo_path=join_request.photo_path,
    )
    db.session.add(new_user)
    db.session.flush()  # so new_user.id exists for the field values below

    for field_id_str, value in (join_request.field_responses or {}).items():
        db.session.add(UserFieldValue(user_id=new_user.id, field_id=int(field_id_str), value=value))

    join_request.status = RequestStatusEnum.APPROVED
    join_request.reviewed_by_id = current_user.id
    db.session.commit()

    flash(f"{new_user.name} has been added.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/requests/<int:request_id>/reject", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def reject_request(request_id):
    join_request = _get_own_join_request_or_404(request_id)

    join_request.status = RequestStatusEnum.REJECTED
    join_request.reviewed_by_id = current_user.id
    join_request.rejection_reason = request.form.get("reason", "").strip() or None
    db.session.commit()

    flash(f"Request from {join_request.name} was rejected.", "info")
    return redirect(url_for("admin.dashboard"))


def _get_own_join_request_or_404(request_id: int) -> JoinRequest:
    """
    Fetch a JoinRequest, but only if it belongs to the logged-in admin's
    own institute — otherwise admin A could approve/reject requests for
    admin B's institute just by guessing an ID in the URL.
    """
    join_request = JoinRequest.query.get_or_404(request_id)
    if join_request.institute_id != current_user.institute_id:
        abort(404)
    return join_request
