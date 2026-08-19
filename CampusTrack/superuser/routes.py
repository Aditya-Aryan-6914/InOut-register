"""
Superuser portal routes — everything under /superuser/*.

Unlike the admin blueprint, nothing here needs an "own institute" IDOR
guard — seeing every institute is the entire point of this role. The
guard that matters here is simpler: @role_required(RoleEnum.SUPERUSER)
on every single route, with no exceptions.
"""
from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import and_, or_

from . import superuser_bp
from ..decorators import role_required
from ..extensions import db
from ..models import (
    CustomField, Institute, InstituteStatusEnum, PlanEnum,
    RequestStatusEnum, Room, RoleEnum, User,
)


@superuser_bp.route("/dashboard")
@role_required(RoleEnum.SUPERUSER)
def dashboard():
    query = Institute.query
    search = request.args.get("q", "").strip()
    if search:
        like = f"%{search}%"
        # Matching on institute name OR an admin's name/email means a
        # superuser can find "that one college" without knowing whether
        # they remember its name or its admin's email.
        query = query.filter(
            Institute.id.in_(
                db.session.query(Institute.id)
                .outerjoin(User, User.institute_id == Institute.id)
                .filter(
                    or_(
                        Institute.name.ilike(like),
                        and_(User.role == RoleEnum.ADMIN, User.name.ilike(like)),
                        and_(User.role == RoleEnum.ADMIN, User.email.ilike(like)),
                    )
                )
            )
        )

    institutes = query.order_by(Institute.name).all()

    # Platform-wide stat strip. Simple counts, not worth a model method
    # since nothing else in the app needs "every institute at once".
    platform_stats = {
        "total_institutes": Institute.query.count(),
        "total_users": User.query.filter_by(role=RoleEnum.USER).count(),
        "total_admins": User.query.filter_by(role=RoleEnum.ADMIN).count(),
        "checkins_today": sum(inst.today_checkin_count for inst in institutes),
    }

    # One admin per institute is the expected shape (see Institute.admins'
    # docstring in models.py), so .first() is the primary contact to show
    # in the table — but don't assume: an institute could theoretically
    # have zero if its sole admin account was ever deleted.
    rows = []
    for inst in institutes:
        rows.append({
            "institute": inst,
            "admin": inst.admins.first(),
            "user_count": inst.active_user_count,
            "room_count": inst.rooms.count(),
        })

    return render_template(
        "superuser/dashboard.html",
        rows=rows,
        platform_stats=platform_stats,
        search=search,
    )


@superuser_bp.route("/institutes/<int:institute_id>")
@role_required(RoleEnum.SUPERUSER)
def institute_detail(institute_id):
    institute = Institute.query.get_or_404(institute_id)

    users = (
        institute.users.filter_by(role=RoleEnum.USER)
        .order_by(User.name)
        .all()
    )
    rooms = institute.rooms.order_by(Room.name).all()
    custom_fields = institute.custom_fields.order_by(CustomField.order).all()
    pending_requests = institute.join_requests.filter_by(status=RequestStatusEnum.PENDING).count()

    return render_template(
        "superuser/institute_detail.html",
        institute=institute,
        admins=list(institute.admins),
        users=users,
        rooms=rooms,
        custom_fields=custom_fields,
        pending_requests=pending_requests,
        currently_in=institute.currently_in_count,
        today_checkins=institute.today_checkin_count,
    )


@superuser_bp.route("/institutes/<int:institute_id>/suspend", methods=["POST"])
@role_required(RoleEnum.SUPERUSER)
def suspend_institute(institute_id):
    institute = Institute.query.get_or_404(institute_id)
    institute.status = InstituteStatusEnum.SUSPENDED
    db.session.commit()
    flash(f"{institute.name} has been suspended — its admin and users can no longer log in.", "success")
    return redirect(request.referrer or url_for("superuser.dashboard"))


@superuser_bp.route("/institutes/<int:institute_id>/activate", methods=["POST"])
@role_required(RoleEnum.SUPERUSER)
def activate_institute(institute_id):
    institute = Institute.query.get_or_404(institute_id)
    institute.status = InstituteStatusEnum.ACTIVE
    db.session.commit()
    flash(f"{institute.name} has been reactivated.", "success")
    return redirect(request.referrer or url_for("superuser.dashboard"))


@superuser_bp.route("/institutes/<int:institute_id>/set-plan", methods=["POST"])
@role_required(RoleEnum.SUPERUSER)
def set_institute_plan(institute_id):
    institute = Institute.query.get_or_404(institute_id)
    new_plan = request.form.get("plan")

    if new_plan not in {p.value for p in PlanEnum}:
        flash("Invalid plan.", "error")
        return redirect(request.referrer or url_for("superuser.dashboard"))

    institute.plan = PlanEnum(new_plan)
    db.session.commit()
    flash(f"{institute.name} is now on the {institute.plan.value} plan.", "success")
    return redirect(request.referrer or url_for("superuser.dashboard"))


@superuser_bp.route("/institutes/<int:institute_id>/delete", methods=["POST"])
@role_required(RoleEnum.SUPERUSER)
def delete_institute(institute_id):
    """
    Deleting an Institute cascades to its Users, CustomFields, Rooms,
    JoinRequests, and (through those) every AttendanceLog and
    UserFieldValue — see the cascade="all, delete-orphan" relationships
    in models.py. This is genuinely destructive and irreversible, which
    is why the confirmation on the frontend requires typing the
    institute's name, not just a plain confirm() dialog.
    """
    institute = Institute.query.get_or_404(institute_id)

    confirm_name = request.form.get("confirm_name", "").strip()
    if confirm_name != institute.name:
        flash("Institute name didn't match — nothing was deleted.", "error")
        return redirect(url_for("superuser.institute_detail", institute_id=institute.id))

    name = institute.name
    db.session.delete(institute)
    db.session.commit()
    flash(f"{name} and all its data have been permanently deleted.", "info")
    return redirect(url_for("superuser.dashboard"))
