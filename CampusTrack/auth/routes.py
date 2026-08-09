from flask import Blueprint, render_template

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/admin/login")
def admin_login():
    return render_template("admin.html")


@auth_bp.route("/user/login")
def user_login():
    return render_template("index.html")
