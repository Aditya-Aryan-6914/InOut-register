import os

from flask import Flask

from .extensions import db, login_manager


def create_app(test_config=None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-change-me"),
        SQLALCHEMY_DATABASE_URI="sqlite:///" + os.path.join(app.instance_path, "inout.db"),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    # Imported here, not at module level, to avoid a circular import
    # between extensions.py and models.py (models.py imports `db` from
    # extensions.py, so extensions.py can't import models.py back at
    # module load time).
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .main import main_bp
    from .auth import auth_bp
    from .admin import admin_bp
    from .user import user_bp
    from .superuser import superuser_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(superuser_bp)

    with app.app_context():
        db.create_all()  # fine for now — swap for Flask-Migrate once the schema stabilizes

    _register_cli(app)

    return app


def _register_cli(app: Flask) -> None:
    """
    Superuser accounts must never be creatable from a public web form —
    anyone who could self-register as superuser would own every institute,
    admin, and user on the platform. There's deliberately no
    `/superuser/signup` route.

    But that means there also has to be *some* way to create the first
    superuser. A CLI command run from a trusted terminal (never over HTTP)
    is the standard, secure answer: it requires shell access to the server
    (SSH key, deploy console, etc.), which is a far smaller trust boundary
    than "anyone who can reach a URL."
    """
    import click
    from .extensions import db
    from .models import RoleEnum, User

    @app.cli.command("create-superuser")
    @click.option("--name", prompt=True)
    @click.option("--email", prompt=True)
    @click.option(
        "--password",
        prompt=True,
        hide_input=True,
        confirmation_prompt=True,
    )
    def create_superuser(name: str, email: str, password: str) -> None:
        """Create a superuser account. Run this from a trusted shell only."""
        email = email.strip().lower()

        if User.query.filter_by(email=email).first():
            click.echo(f"Error: an account with email {email!r} already exists.")
            return

        if len(password) < 8:
            click.echo("Error: password must be at least 8 characters.")
            return

        user = User(
            role=RoleEnum.SUPERUSER,
            institute_id=None,
            name=name.strip(),
            email=email,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        click.echo(f"Superuser created: {email}")