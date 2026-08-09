from .extensions import db


class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False, unique=True)
    mobile_no = db.Column(db.String(15), nullable=False, unique=True)
    institute = db.Column(db.String(50), nullable=False)
    fields_required = db.Column(db.String(200), nullable=False)

    def __repr__(self) -> str:
        return f"<Admin {self.name} ({self.institute})>"
