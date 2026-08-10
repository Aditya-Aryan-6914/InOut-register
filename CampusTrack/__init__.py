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

    return app
