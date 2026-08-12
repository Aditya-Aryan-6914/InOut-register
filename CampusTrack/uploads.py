"""
File upload helpers.

Two kinds of upload happen at registration:
  1. The profile photo (always required — this becomes the reference
     image for face-match verification at check-in later).
  2. Any FILE-type custom field the admin added (e.g. "ID Proof").

Both save into CampusTrack/static/uploads/... and return a path
relative to the static folder, so callers can do:
    url_for('static', filename=saved_path)

SECURITY NOTE: files saved here are served directly by Flask's static
handler with no access control — anyone with the (random, unguessable)
URL can view them. Fine for a mini project; before this goes anywhere
real, move uploads outside `static/` and serve them through an
authenticated route instead (check current_user's role/institute
before returning the file).
"""
import os
import uuid

from flask import current_app
from PIL import Image, UnidentifiedImageError

ALLOWED_FILE_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
MAX_UPLOAD_MB = 5


class UploadError(ValueError):
    """Raised on invalid uploads; message is safe to show the user directly."""


def _ensure_dir(abs_path: str) -> None:
    os.makedirs(os.path.dirname(abs_path), exist_ok=True)


def _static_folder() -> str:
    folder = current_app.static_folder
    if not folder:
        raise RuntimeError("This app has no static folder configured; can't save uploads.")
    return folder


def save_photo_upload(file_storage, subfolder: str = "photos") -> str:
    """
    Validates and saves a profile photo. Re-encodes through Pillow
    (rather than trusting the uploaded bytes as-is) so a file that's
    merely renamed to look like an image, but isn't one, gets rejected
    instead of silently stored.
    """
    if not file_storage or not file_storage.filename:
        raise UploadError("Please choose a photo.")

    try:
        img = Image.open(file_storage.stream)
        img.verify()
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)  # re-open: verify() invalidates the handle
        img = img.convert("RGB")
    except (UnidentifiedImageError, OSError):
        raise UploadError("That doesn't look like a valid image file.")

    filename = f"{uuid.uuid4().hex}.jpg"
    rel_path = f"uploads/{subfolder}/{filename}"
    abs_path = os.path.join(_static_folder(), "uploads", subfolder, filename)
    _ensure_dir(abs_path)
    img.save(abs_path, format="JPEG", quality=88)
    return rel_path


def save_generic_file(file_storage, subfolder: str = "files") -> str:
    """Validates and saves a non-photo upload (e.g. a PDF ID proof)."""
    if not file_storage or not file_storage.filename:
        raise UploadError("Please choose a file.")

    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in ALLOWED_FILE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        raise UploadError(f"Unsupported file type '.{ext}'. Allowed: {allowed}.")

    filename = f"{uuid.uuid4().hex}.{ext}"
    rel_path = f"uploads/{subfolder}/{filename}"
    abs_path = os.path.join(_static_folder(), "uploads", subfolder, filename)
    _ensure_dir(abs_path)
    file_storage.save(abs_path)
    return rel_path
