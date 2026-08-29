"""
Admin portal routes — everything under /admin/*.

Note: your existing bare "/admin" route (the public admin landing page,
per your README) is untouched — it presumably lives in the `main`
blueprint. Everything here sits one level deeper (/admin/dashboard,
/admin/fields, ...) so there's no collision.
"""
import io
import secrets

import qrcode
from flask import abort, flash, jsonify, redirect, render_template, request, send_file, url_for
from flask_login import current_user
from sqlalchemy.exc import IntegrityError

from . import admin_bp
from ..decorators import role_required
from ..extensions import db
from ..models import (
    CustomField, FaceReviewFlag, FaceSampleSourceEnum, FieldTypeEnum, JoinRequest,
    RequestStatusEnum, Room, RoleEnum, User, UserFacePhoto, UserFieldValue,
)
from ..qr_utils import make_qr_payload

OPTION_FIELD_TYPES = {FieldTypeEnum.DROPDOWN.value, FieldTypeEnum.CHECKBOX.value}
MAX_ROOMS_PER_INSTITUTE = 500


@admin_bp.route("/dashboard")
@role_required(RoleEnum.ADMIN)
def dashboard():
    institute = current_user.institute
    custom_fields = institute.custom_fields.order_by(CustomField.order).all()

    pending_requests = (
        institute.join_requests.filter_by(status=RequestStatusEnum.PENDING)
        .order_by(JoinRequest.created_at.desc())
        .all()
    )

    pending_face_flags = (
        FaceReviewFlag.query.join(User, FaceReviewFlag.user_id == User.id)
        .filter(User.institute_id == institute.id, FaceReviewFlag.resolved.is_(False))
        .count()
    )

    return render_template(
        "admin/dashboard.html",
        institute=institute,
        active_users=institute.active_user_count,
        currently_in=institute.currently_in_count,
        today_checkins=institute.today_checkin_count,
        rooms=institute.rooms.order_by(Room.name).all(),
        custom_fields=custom_fields,
        pending_requests=pending_requests,
        pending_face_flags=pending_face_flags,
    )


@admin_bp.route("/dashboard/live-counts")
@role_required(RoleEnum.ADMIN)
def live_counts():
    """
    Polled by the dashboard every ~12s (see static/js/admin_dashboard.js)
    to refresh the stat cards and per-room table without a full page
    reload. Scoped to current_user.institute the same way every other
    admin route is — an admin can only ever see their own institute's
    numbers here.
    """
    institute = current_user.institute
    active_users = institute.active_user_count
    currently_in = institute.currently_in_count

    return jsonify({
        "active_users": active_users,
        "currently_in": currently_in,
        "currently_out": active_users - currently_in,
        "today_checkins": institute.today_checkin_count,
        "pending_count": institute.pending_request_count,
        "rooms": [
            {
                "id": room.id,
                "currently_in": room.currently_in_count,
                "last_checkin_at": room.last_checkin_at.isoformat() if room.last_checkin_at else None,
            }
            for room in institute.rooms.all()
        ],
    })


@admin_bp.route("/fields")
@role_required(RoleEnum.ADMIN)
def fields():
    institute = current_user.institute
    custom_fields = institute.custom_fields.order_by(CustomField.order).all()

    # How many users have already answered each field — shown in the UI
    # so an admin doesn't casually delete a field with real data behind it.
    response_counts = {cf.id: cf.values.count() for cf in custom_fields}

    return render_template(
        "admin/fields.html",
        institute=institute,
        custom_fields=custom_fields,
        response_counts=response_counts,
        field_types=[t.value for t in FieldTypeEnum],
    )


class FieldValidationError(ValueError):
    """Raised by _validate_field_payload; message is safe to show the admin directly."""


@admin_bp.route("/fields/save", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def save_fields():
    """
    Replaces the institute's entire field set with whatever the
    drag-and-drop canvas currently holds. The frontend sends the full
    ordered list on every save (not incremental add/remove calls) —
    simpler to reason about and keeps the whole change atomic.
    """
    institute = current_user.institute
    payload = request.get_json(silent=True)

    if not payload or not isinstance(payload.get("fields"), list):
        return jsonify({"error": "Invalid request."}), 400

    try:
        cleaned = _validate_field_payload(payload["fields"])
    except FieldValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    # Fields that already belong to THIS institute — anything else
    # submitted (e.g. a stale/foreign id) is treated as a brand-new
    # field for this institute rather than touching someone else's row.
    existing = {cf.id: cf for cf in institute.custom_fields}
    kept_ids = set()

    for f in cleaned:
        cf = existing.get(f["id"]) if f["id"] else None
        if cf is not None:
            cf.label = f["label"]
            cf.field_type = FieldTypeEnum(f["field_type"])
            cf.is_required = f["is_required"]
            cf.options = f["options"]
            cf.order = f["order"]
            kept_ids.add(cf.id)
        else:
            db.session.add(CustomField(
                institute_id=institute.id,
                label=f["label"],
                field_type=FieldTypeEnum(f["field_type"]),
                is_required=f["is_required"],
                options=f["options"],
                order=f["order"],
            ))

    for cf_id, cf in existing.items():
        if cf_id not in kept_ids:
            db.session.delete(cf)  # cascades to UserFieldValue rows for this field

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Two fields ended up with the same name. Please use unique labels."}), 400

    return jsonify({"success": True})


def _validate_field_payload(incoming: list) -> list:
    """Returns the cleaned field list, or raises FieldValidationError."""
    if len(incoming) > 50:
        raise FieldValidationError("A form can have at most 50 fields.")

    valid_types = {t.value for t in FieldTypeEnum}
    seen_labels = set()
    cleaned = []

    for idx, f in enumerate(incoming):
        label = str(f.get("label", "")).strip()
        field_type = f.get("field_type")

        if not label or len(label) > 100:
            raise FieldValidationError(f"Field {idx + 1} needs a label under 100 characters.")
        if field_type not in valid_types:
            raise FieldValidationError(f"'{label}' has an invalid field type.")

        label_key = label.lower()
        if label_key in seen_labels:
            raise FieldValidationError(f"Duplicate field label: '{label}'.")
        seen_labels.add(label_key)

        options = None
        if field_type in OPTION_FIELD_TYPES:
            raw_options = f.get("options") or []
            options = [str(o).strip() for o in raw_options if str(o).strip()]
            if not options:
                raise FieldValidationError(f"'{label}' needs at least one option.")

        field_id = f.get("id")
        cleaned.append({
            "id": int(field_id) if field_id else None,
            "label": label,
            "field_type": field_type,
            "is_required": bool(f.get("is_required", True)),
            "options": options,
            "order": idx,
        })

    return cleaned


@admin_bp.route("/rooms")
@role_required(RoleEnum.ADMIN)
def rooms():
    institute = current_user.institute
    room_list = institute.rooms.order_by(Room.created_at).all()
    return render_template(
        "admin/rooms.html",
        institute=institute,
        rooms=room_list,
        max_rooms=MAX_ROOMS_PER_INSTITUTE,
    )


@admin_bp.route("/rooms/generate", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def generate_rooms():
    institute = current_user.institute

    try:
        count = int(request.form.get("count", "0"))
    except ValueError:
        count = 0

    existing_count = institute.rooms.count()
    if count < 1:
        flash("Enter at least 1 room to generate.", "error")
        return redirect(url_for("admin.rooms"))
    if existing_count + count > MAX_ROOMS_PER_INSTITUTE:
        flash(f"You can track at most {MAX_ROOMS_PER_INSTITUTE} rooms in total.", "error")
        return redirect(url_for("admin.rooms"))

    name_prefix = request.form.get("name_prefix", "Room").strip() or "Room"

    for i in range(count):
        db.session.add(Room(
            institute_id=institute.id,
            name=f"{name_prefix} {existing_count + i + 1}",
            qr_token=secrets.token_urlsafe(12),
        ))

    db.session.commit()
    flash(f"{count} room{'s' if count != 1 else ''} created, each with its own QR code.", "success")
    return redirect(url_for("admin.rooms"))


@admin_bp.route("/rooms/<int:room_id>/qr.png")
@role_required(RoleEnum.ADMIN)
def room_qr_image(room_id):
    room = _get_own_room_or_404(room_id)
    payload = make_qr_payload(room)

    img = qrcode.make(payload)
    buffer = io.BytesIO()
    # qrcode's bundled type stub omits `format` from save() even though
    # the real implementation (qrcode/image/pil.py) accepts and uses it —
    # verified against the installed package source, not guessed.
    img.save(buffer, format="PNG")  # type: ignore[reportCallIssue]
    buffer.seek(0)
    return send_file(buffer, mimetype="image/png")


@admin_bp.route("/rooms/<int:room_id>/rename", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def rename_room(room_id):
    room = _get_own_room_or_404(room_id)
    new_name = request.form.get("name", "").strip()

    if not new_name:
        flash("Room name can't be empty.", "error")
        return redirect(url_for("admin.rooms"))

    room.name = new_name
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f"You already have a room named '{new_name}'.", "error")
        return redirect(url_for("admin.rooms"))

    flash("Room renamed.", "success")
    return redirect(url_for("admin.rooms"))


@admin_bp.route("/rooms/<int:room_id>/set-location", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def set_room_location(room_id):
    """
    Saves the room's geofence center. Meant to be called from the
    rooms page while the admin is physically standing at the room,
    using the browser's own geolocation — see the "Set location"
    button in rooms.html. AJAX endpoint (JSON in, JSON out) so the
    page doesn't need a full reload for something this quick.
    """
    room = _get_own_room_or_404(room_id)
    payload = request.get_json(silent=True) or {}

    try:
        latitude = float(payload.get("latitude", ""))
        longitude = float(payload.get("longitude", ""))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid coordinates."}), 400

    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return jsonify({"error": "Coordinates out of range."}), 400

    radius = payload.get("radius_m")
    if radius is not None:
        try:
            radius = int(radius)
            if not (10 <= radius <= 1000):
                return jsonify({"error": "Radius must be between 10 and 1000 meters."}), 400
            room.geofence_radius_m = radius
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid radius."}), 400

    room.latitude = latitude
    room.longitude = longitude
    db.session.commit()

    return jsonify({
        "success": True,
        "latitude": room.latitude,
        "longitude": room.longitude,
        "radius_m": room.geofence_radius_m,
    })


@admin_bp.route("/rooms/<int:room_id>/delete", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def delete_room(room_id):
    room = _get_own_room_or_404(room_id)
    log_count = room.attendance_logs.count()

    db.session.delete(room)
    db.session.commit()

    if log_count:
        flash(f"Room deleted, along with {log_count} attendance record(s).", "info")
    else:
        flash("Room deleted.", "success")
    return redirect(url_for("admin.rooms"))


def _get_own_room_or_404(room_id: int) -> Room:
    """Same guard as _get_own_join_request_or_404 — see its docstring."""
    room = Room.query.get_or_404(room_id)
    if room.institute_id != current_user.institute_id:
        abort(404)
    return room


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

    # Seed face-match sample #1 from the registration photo. Kept as
    # its own UserFacePhoto row (not just relying on User.photo_path)
    # so it trains alongside anything the user later adds via
    # "Improve Face" — see User.face_sample_rel_paths().
    if join_request.photo_path:
        db.session.add(UserFacePhoto(
            user_id=new_user.id,
            photo_path=join_request.photo_path,
            source=FaceSampleSourceEnum.REGISTRATION,
        ))

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


# =================================================================
# Face review flags — raised automatically (see user/routes.py
# submit_improve_face) when someone's "Improve Face" capture doesn't
# closely match their existing samples. Doesn't block the user, just
# surfaces the case here so an admin can confirm it's really them
# (or catch someone trying to register a different person's face).
# =================================================================

@admin_bp.route("/face-flags")
@role_required(RoleEnum.ADMIN)
def face_flags():
    flags = (
        FaceReviewFlag.query.join(User, FaceReviewFlag.user_id == User.id)
        .filter(User.institute_id == current_user.institute_id, FaceReviewFlag.resolved.is_(False))
        .order_by(FaceReviewFlag.created_at.desc())
        .all()
    )
    return render_template("admin/face_flags.html", flags=flags)


@admin_bp.route("/face-flags/<int:flag_id>/approve", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def approve_face_flag(flag_id):
    """Confirms it really is the same person — keeps the new sample, clears the flag."""
    flag = _get_own_face_flag_or_404(flag_id)
    flag.resolved = True
    flag.resolved_by_id = current_user.id
    flag.resolved_at = db.func.now()
    db.session.commit()
    flash("Face sample approved.", "success")
    return redirect(url_for("admin.face_flags"))


@admin_bp.route("/face-flags/<int:flag_id>/revert", methods=["POST"])
@role_required(RoleEnum.ADMIN)
def revert_face_flag(flag_id):
    """Rejects the flagged sample entirely — deletes it so it stops being used to verify check-ins."""
    flag = _get_own_face_flag_or_404(flag_id)
    if flag.new_face_photo is not None:
        db.session.delete(flag.new_face_photo)
    flag.resolved = True
    flag.resolved_by_id = current_user.id
    flag.resolved_at = db.func.now()
    db.session.commit()
    flash("Flagged face sample was removed.", "info")
    return redirect(url_for("admin.face_flags"))


def _get_own_face_flag_or_404(flag_id: int) -> FaceReviewFlag:
    """Same institute-scoping guard as _get_own_join_request_or_404."""
    flag = FaceReviewFlag.query.get_or_404(flag_id)
    if flag.user.institute_id != current_user.institute_id:
        abort(404)
    return flag
