from .extensions import db
"""
CampusTrack — Database Models
==============================
Flask-SQLAlchemy schema covering: Institute, User (role-based), CustomField,
JoinRequest, UserFieldValue, Room, AttendanceLog.

PROJECT STRUCTURE ASSUMPTION
-----------------------------
This file assumes the app-factory + blueprint pattern we discussed, with a
single shared `db` instance living in `extensions.py`:

    # extensions.py
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

    # app.py
    from extensions import db
    def create_app():
        app = Flask(__name__)
        db.init_app(app)
        ...

If you'd rather keep everything in one file for now, just replace the
import below with `db = SQLAlchemy()` directly in this file — everything
else works unchanged. Either way, run this through Flask-Migrate
(`flask db init / migrate / upgrade`) rather than `db.create_all()` once
you start changing the schema, or you'll lose data on every tweak.

ONE ADDITION BEYOND THE ORIGINAL LIST
--------------------------------------
You asked for Institute, User, CustomField, Room, AttendanceLog and
JoinRequest. I've added one more: **UserFieldValue**. Reasoning: CustomField
defines the *questions* an institute asks (e.g. "Room No."), but something
has to store each user's *answers*. JoinRequest holds answers temporarily
as JSON while a request is pending (cheap, since it's short-lived and
gets deleted after review). Once approved, those answers are copied into
UserFieldValue as proper rows — so anything long-lived and queryable
(e.g. "find everyone in Room 204") stays normalized, while the throwaway
pending-request data doesn't need its own table.
"""

from datetime import datetime
import enum

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from extensions import db


# =============================================================
# Enums
# =============================================================

class RoleEnum(enum.Enum):
    SUPERUSER = "superuser"
    ADMIN = "admin"
    USER = "user"


class InstituteStatusEnum(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatusEnum(enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class PlanEnum(enum.Enum):
    FREE = "free"            # ad-supported tier
    SUBSCRIBED = "subscribed"  # one-time-subscription tier


class FieldTypeEnum(enum.Enum):
    TEXT = "text"
    NUMBER = "number"
    DATE = "date"
    DROPDOWN = "dropdown"
    CHECKBOX = "checkbox"
    FILE = "file"
    EMAIL = "email"
    PHONE = "phone"


class RequestStatusEnum(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class EventTypeEnum(enum.Enum):
    CHECK_IN = "check_in"
    CHECK_OUT = "check_out"


# =============================================================
# Mixin
# =============================================================

class TimestampMixin:
    """Adds created_at / updated_at to any model that inherits it."""
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


# =============================================================
# Institute
# =============================================================

class Institute(db.Model, TimestampMixin):
    """
    One row per hostel / college / apartment complex. Owns its own set of
    CustomFields and Rooms. The "admin" of an institute is just a User row
    with role=ADMIN and institute_id pointing here — no separate owner_id
    column, which avoids a circular foreign key between Institute and User.
    """
    __tablename__ = "institutes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False, index=True)
    address = db.Column(db.String(255), nullable=True)

    # Join password: what a prospective USER enters at registration to
    # prove they belong to this institute. Hashed like a real password —
    # it's a low-security gate (shared secret), so pair it in the app
    # layer with admin approval and/or an email-domain check, not alone.
    join_password_hash = db.Column(db.String(255), nullable=False)

    status = db.Column(
        db.Enum(InstituteStatusEnum), default=InstituteStatusEnum.ACTIVE, nullable=False
    )
    plan = db.Column(db.Enum(PlanEnum), default=PlanEnum.FREE, nullable=False)
    plan_expires_at = db.Column(db.DateTime, nullable=True)

    # --- Relationships ---
    # lazy="dynamic" returns a query object instead of a list, so you can
    # chain .filter_by()/.count() on institute.users without loading
    # every row into memory — matters once an institute has 1000+ users.
    users = db.relationship(
        "User", backref="institute", lazy="dynamic",
        foreign_keys="User.institute_id",
        cascade="all, delete-orphan",
    )
    custom_fields = db.relationship(
        "CustomField", backref="institute", lazy="dynamic",
        order_by="CustomField.order",
        cascade="all, delete-orphan",
    )
    rooms = db.relationship(
        "Room", backref="institute", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    join_requests = db.relationship(
        "JoinRequest", backref="institute", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    # --- Helpers ---
    def set_join_password(self, raw_password: str) -> None:
        self.join_password_hash = generate_password_hash(raw_password)

    def check_join_password(self, raw_password: str) -> bool:
        return check_password_hash(self.join_password_hash, raw_password)

    @property
    def admins(self):
        """All User rows with role=ADMIN belonging to this institute."""
        return self.users.filter_by(role=RoleEnum.ADMIN)

    @property
    def active_user_count(self) -> int:
        return self.users.filter_by(role=RoleEnum.USER, status=UserStatusEnum.ACTIVE).count()

    @property
    def pending_request_count(self) -> int:
        return self.join_requests.filter_by(status=RequestStatusEnum.PENDING).count()

    def __repr__(self):
        return f"<Institute {self.id} {self.name!r}>"


# =============================================================
# User  (superuser / admin / user — one table, one role column)
# =============================================================

class User(db.Model, UserMixin, TimestampMixin):
    """
    One table for all three roles. UserMixin (Flask-Login) supplies
    is_authenticated / is_active / get_id() etc. for free.

    - SUPERUSER: institute_id is NULL (belongs to the platform, not one institute).
    - ADMIN: institute_id points to the institute they own/manage.
    - USER (student/resident/worker): institute_id points to their institute;
      only created once their JoinRequest is approved (see below).
    """
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    role = db.Column(db.Enum(RoleEnum), nullable=False, default=RoleEnum.USER, index=True)

    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=True, index=True
    )

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=False, unique=True, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)

    # Path/key to the stored photo (filesystem path or cloud object key —
    # store the file itself outside the DB). Used both for display and as
    # the reference image for face-match verification at check-in.
    photo_path = db.Column(db.String(255), nullable=True)

    status = db.Column(db.Enum(UserStatusEnum), default=UserStatusEnum.ACTIVE, nullable=False)

    # --- Relationships ---
    field_values = db.relationship(
        "UserFieldValue", backref="user", lazy="dynamic",
        cascade="all, delete-orphan",
    )
    attendance_logs = db.relationship(
        "AttendanceLog", backref="user", lazy="dynamic",
        foreign_keys="AttendanceLog.user_id",
        cascade="all, delete-orphan",
    )

    # --- Helpers ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self) -> bool:
        return self.role == RoleEnum.ADMIN

    @property
    def is_superuser(self) -> bool:
        return self.role == RoleEnum.SUPERUSER

    @property
    def last_attendance_event(self):
        """Most recent check-in/out row — the basis of a live 'In'/'Out' badge."""
        return self.attendance_logs.order_by(AttendanceLog.timestamp.desc()).first()

    @property
    def current_status(self) -> str:
        last = self.last_attendance_event
        if last is None:
            return "unknown"
        return "in" if last.event_type == EventTypeEnum.CHECK_IN else "out"

    def __repr__(self):
        return f"<User {self.id} {self.email!r} role={self.role.value}>"


# =============================================================
# CustomField  (the admin's drag-and-drop form definition)
# =============================================================

class CustomField(db.Model, TimestampMixin):
    """
    One row per field the admin has added to their registration form
    (e.g. "Room No.", type=text, required=True, order=2).
    `options` holds the choice list for DROPDOWN/CHECKBOX types as JSON,
    e.g. ["Block A", "Block B", "Block C"]; NULL for other field types.
    """
    __tablename__ = "custom_fields"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    label = db.Column(db.String(100), nullable=False)          # "Room Number"
    field_type = db.Column(db.Enum(FieldTypeEnum), nullable=False)
    options = db.Column(db.JSON, nullable=True)                 # for dropdown/checkbox
    is_required = db.Column(db.Boolean, default=True, nullable=False)
    order = db.Column(db.Integer, default=0, nullable=False)    # drag-and-drop position

    # --- Relationships ---
    values = db.relationship(
        "UserFieldValue", backref="field", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("institute_id", "label", name="uq_field_label_per_institute"),
    )

    def __repr__(self):
        return f"<CustomField {self.id} {self.label!r} ({self.field_type.value})>"


# =============================================================
# JoinRequest  (pending registration, awaiting admin approval)
# =============================================================

class JoinRequest(db.Model, TimestampMixin):
    """
    Created when someone fills the registration form. Holds everything
    needed to create a real User later, INCLUDING their chosen password
    (hashed) and their custom-field answers as a JSON blob — deliberately
    denormalized here since a request is short-lived (reviewed within
    days, then converted or deleted) and never needs field-by-field
    querying the way an active user's data does.

    field_responses shape: { "<custom_field_id>": "<value>", ... }
    """
    __tablename__ = "join_requests"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    photo_path = db.Column(db.String(255), nullable=True)

    field_responses = db.Column(db.JSON, nullable=True)

    status = db.Column(
        db.Enum(RequestStatusEnum), default=RequestStatusEnum.PENDING, nullable=False, index=True
    )
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)

    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def __repr__(self):
        return f"<JoinRequest {self.id} {self.email!r} status={self.status.value}>"


# =============================================================
# UserFieldValue  (an approved user's answer to one CustomField)
# =============================================================

class UserFieldValue(db.Model):
    """
    Normalized storage for an active user's custom-field answers, e.g.
    (user_id=42, field_id=3, value="204"). Created by copying the
    matching JoinRequest.field_responses entries at approval time.
    """
    __tablename__ = "user_field_values"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    field_id = db.Column(
        db.Integer, db.ForeignKey("custom_fields.id", ondelete="CASCADE"), nullable=False, index=True
    )
    value = db.Column(db.String(255), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("user_id", "field_id", name="uq_value_per_user_field"),
    )

    def __repr__(self):
        return f"<UserFieldValue user={self.user_id} field={self.field_id}>"


# =============================================================
# Room  (a checkpoint the admin tracks — one QR code each)
# =============================================================

class Room(db.Model, TimestampMixin):
    """
    One row per checkpoint the admin wants attendance tracked for
    (a hostel room, a classroom, a building gate...). Created in bulk
    when the admin sets "how many rooms/checkpoints to track."

    qr_token is the public identifier embedded in the room's QR code.
    Keep the QR *payload* itself signed at the application layer (e.g.
    itsdangerous.URLSafeTimedSerializer over f"{institute_id}:{qr_token}")
    so a scanned code can be verified without a DB round trip and can't
    be forged by guessing sequential IDs. The raw image file doesn't need
    to live in the DB — regenerate it from qr_token on demand, or cache
    it at qr_image_path.
    """
    __tablename__ = "rooms"

    id = db.Column(db.Integer, primary_key=True)
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True
    )

    name = db.Column(db.String(100), nullable=False)       # "Room 204", "Block B Gate"
    qr_token = db.Column(db.String(64), nullable=False, unique=True, index=True)
    qr_image_path = db.Column(db.String(255), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # Optional: latitude/longitude of this checkpoint, used as the center
    # of the geo-fence radius check at verification time.
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    geofence_radius_m = db.Column(db.Integer, default=100, nullable=False)

    attendance_logs = db.relationship(
        "AttendanceLog", backref="room", lazy="dynamic",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.UniqueConstraint("institute_id", "name", name="uq_room_name_per_institute"),
    )

    @property
    def currently_in_count(self) -> int:
        """
        Users whose most recent event AT THIS ROOM was a check-in.
        Fine for a mini project / moderate traffic; if this gets called
        often on a busy dashboard, replace with a maintained counter
        column updated inside the check-in/out transaction instead of
        recomputing from the full log every request.
        """
        sub = (
            db.session.query(
                AttendanceLog.user_id,
                db.func.max(AttendanceLog.timestamp).label("latest"),
            )
            .filter(AttendanceLog.room_id == self.id)
            .group_by(AttendanceLog.user_id)
            .subquery()
        )
        return (
            db.session.query(AttendanceLog)
            .join(
                sub,
                db.and_(
                    AttendanceLog.user_id == sub.c.user_id,
                    AttendanceLog.timestamp == sub.c.latest,
                ),
            )
            .filter(
                AttendanceLog.room_id == self.id,
                AttendanceLog.event_type == EventTypeEnum.CHECK_IN,
            )
            .count()
        )

    def __repr__(self):
        return f"<Room {self.id} {self.name!r}>"


# =============================================================
# AttendanceLog  (one row per scan event)
# =============================================================

class AttendanceLog(db.Model):
    """
    One row per verified scan — a check-in OR a check-out, not a pair.
    Deriving "is this person currently in?" from "their most recent
    event" (see User.current_status / Room.currently_in_count) is
    simpler and more auditable than trying to maintain paired rows.
    """
    __tablename__ = "attendance_logs"

    id = db.Column(db.Integer, primary_key=True)

    # Denormalized institute_id: every log row already implies an
    # institute via user/room, but having it directly here makes
    # institute-wide dashboard queries (e.g. "all check-ins today for
    # institute X") a single indexed WHERE instead of a join through
    # both user and room every time.
    institute_id = db.Column(
        db.Integer, db.ForeignKey("institutes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    room_id = db.Column(
        db.Integer, db.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False, index=True
    )

    event_type = db.Column(db.Enum(EventTypeEnum), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # --- Verification breakdown: keep each factor's result separately,
    # not just one pass/fail flag, so admins can see WHICH check failed
    # on a flagged entry instead of a black box.
    qr_verified = db.Column(db.Boolean, default=False, nullable=False)
    face_verified = db.Column(db.Boolean, default=False, nullable=False)
    face_match_score = db.Column(db.Float, nullable=True)   # e.g. 0.0–1.0 similarity
    location_verified = db.Column(db.Boolean, default=False, nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)

    is_flagged = db.Column(db.Boolean, default=False, nullable=False, index=True)
    flag_reason = db.Column(db.String(255), nullable=True)

    device_info = db.Column(db.String(255), nullable=True)  # user agent / device id, for audit

    __table_args__ = (
        db.Index("ix_attendance_institute_timestamp", "institute_id", "timestamp"),
        db.Index("ix_attendance_user_timestamp", "user_id", "timestamp"),
    )

    @property
    def is_fully_verified(self) -> bool:
        return self.qr_verified and self.face_verified and self.location_verified

    def __repr__(self):
        return f"<AttendanceLog {self.id} user={self.user_id} {self.event_type.value} @ {self.timestamp}>"