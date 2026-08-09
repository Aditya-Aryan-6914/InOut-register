from flask import Blueprint, render_template

main_bp = Blueprint("main", __name__, template_folder="../templates")


@main_bp.route("/")
def home():
    return render_template("index.html")


@main_bp.route("/admin")
def admin():
    return render_template("admin.html")
