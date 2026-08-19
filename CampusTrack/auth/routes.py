"""
Login/logout for all three roles, plus the admin signup flow (an admin
account and its institute are created together — see admin_signup()).

One shared `_handle_login()` helper backs three thin route functions
(admin/user/superuser) rather than three near-identical copy-pasted
blocks — the only thing that differs between them is which role to
check against, which template to render, and where to land afterwards.
"""
import re
from urllib.parse import urlparse

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func

from . import auth_bp
from ..extensions import db
from ..models import Institute, RoleEnum, User

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _is_safe_next(target: str | None) -> bool:
    """
    Only follow `next` if it's a plain relative path on this same site.
    Without this check, a link like /user/login?next=https://evil.example
    would send a freshly-logged-in user straight to an attacker's site —
    a classic open-redirect vulnerability.
    """
    if not target:
        return False
    parsed = urlparse(target)
    return not parsed.scheme and not parsed.netloc and target.startswith("/")


def _handle_login(role: RoleEnum, template_name: str, dashboard_endpoint: str):
    if current_user.is_authenticated:
        return redirect(url_for(dashboard_endpoint))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email, role=role).first()

        if user is None or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return render_template(template_name), 401

        if user.status.value == "suspended":
            flash("This account has been suspended. Contact your institute admin.", "error")
            return render_template(template_name), 403

        # A suspended INSTITUTE (superuser action) should block its admin/user
        # logins too, not just new registrations — otherwise "suspend" only
        # stops new signups while everyone already in keeps full access.
        # Superusers have no institute (institute_id is None) so this never
        # applies to them.
        if user.institute is not None and user.institute.status.value == "suspended":
            flash("Your institute's access has been suspended. Contact the platform administrator.", "error")
            return render_template(template_name), 403

        login_user(user)
        next_url = request.args.get("next")
        if next_url and _is_safe_next(next_url):
            return redirect(next_url)
        return redirect(url_for(dashboard_endpoint))

    return render_template(template_name)


@auth_bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    return _handle_login(RoleEnum.ADMIN, "auth/admin_login.html", "admin.dashboard")


@auth_bp.route("/user/login", methods=["GET", "POST"])
def user_login():
    return _handle_login(RoleEnum.USER, "auth/user_login.html", "user.dashboard")


@auth_bp.route("/superuser/login", methods=["GET", "POST"])
def superuser_login():
    return _handle_login(RoleEnum.SUPERUSER, "auth/superuser_login.html", "superuser.dashboard")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.home"))


# =================================================================
# Admin signup — creates an Institute AND its owning Admin account
# together in one form, since an institute doesn't exist without
# someone to administer it.
# =================================================================

def _validate_admin_signup(form: dict, inst_pw: str, inst_pw_confirm: str,
                            admin_pw: str, admin_pw_confirm: str) -> list[str]:
    errors = []

    if len(form["institute_name"]) < 2:
        errors.append("Institute name must be at least 2 characters.")

    if len(form["admin_name"]) < 2:
        errors.append("Your name must be at least 2 characters.")

    if not EMAIL_RE.match(form["admin_email"]):
        errors.append("Enter a valid email address.")
    elif User.query.filter_by(email=form["admin_email"]).first():
        errors.append("An account with this email already exists. Try logging in instead.")

    if len(inst_pw) < 6:
        errors.append("Institute password must be at least 6 characters.")
    elif inst_pw != inst_pw_confirm:
        errors.append("Institute password and confirmation don't match.")

    if len(admin_pw) < 8:
        errors.append("Your account password must be at least 8 characters.")
    elif admin_pw != admin_pw_confirm:
        errors.append("Account password and confirmation don't match.")

    return errors


@auth_bp.route("/admin/signup", methods=["GET", "POST"])
def admin_signup():
    if current_user.is_authenticated:
        target = "admin.dashboard" if current_user.role == RoleEnum.ADMIN else "main.home"
        return redirect(url_for(target))

    form = {
        "institute_name": "",
        "institute_address": "",
        "admin_name": "",
        "admin_email": "",
    }
    duplicate_institute = None

    if request.method == "POST":
        form = {
            "institute_name": request.form.get("institute_name", "").strip(),
            "institute_address": request.form.get("institute_address", "").strip(),
            "admin_name": request.form.get("admin_name", "").strip(),
            "admin_email": request.form.get("admin_email", "").strip().lower(),
        }
        inst_pw = request.form.get("institute_password", "")
        inst_pw_confirm = request.form.get("institute_password_confirm", "")
        admin_pw = request.form.get("admin_password", "")
        admin_pw_confirm = request.form.get("admin_password_confirm", "")

        errors = _validate_admin_signup(form, inst_pw, inst_pw_confirm, admin_pw, admin_pw_confirm)

        if not errors:
            institute = Institute(
                name=form["institute_name"],
                address=form["institute_address"] or None,
            )
            institute.set_join_password(inst_pw)
            db.session.add(institute)
            db.session.flush()  # so institute.id exists for the admin user below

            admin = User(
                role=RoleEnum.ADMIN,
                institute_id=institute.id,
                name=form["admin_name"],
                email=form["admin_email"],
            )
            admin.set_password(admin_pw)
            db.session.add(admin)
            db.session.commit()

            login_user(admin)
            flash(f"Welcome to CampusTrack, {admin.name}! Your institute has been created.", "success")
            return redirect(url_for("admin.dashboard"))

        for error in errors:
            flash(error, "error")

    # Non-blocking heads-up if the institute name looks like a possible
    # duplicate — doesn't stop signup (names aren't required to be
    # globally unique), just helps catch an honest mistake.
    if form["institute_name"]:
        duplicate_institute = Institute.query.filter(
            func.lower(Institute.name) == form["institute_name"].lower()
        ).first()

    return render_template(
        "auth/admin_signup.html",
        form=form,
        duplicate_institute=duplicate_institute,
    )
