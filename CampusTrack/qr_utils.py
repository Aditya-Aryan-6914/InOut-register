"""
Signed QR payload helpers.

A Room's QR code doesn't just encode its database ID — that would let
anyone forge a valid-looking QR by guessing sequential numbers. Instead
we sign a small payload with the app's SECRET_KEY, so a scanner can
verify a code came from us without a database round trip, and a scan
endpoint (built in a later step) can reject anything that wasn't
actually issued by CampusTrack.

Usage:
    from ..qr_utils import make_qr_payload, verify_qr_payload

    token_string = make_qr_payload(room)          # -> put this IN the QR image
    data = verify_qr_payload(token_string)         # -> {"i": ..., "r": ..., "t": ...} or None
"""
from itsdangerous import BadSignature, URLSafeSerializer
from flask import current_app


def _serializer() -> URLSafeSerializer:
    return URLSafeSerializer(current_app.config["SECRET_KEY"], salt="campustrack-qr")


def make_qr_payload(room) -> str:
    """Build the signed string that gets encoded into a room's QR image."""
    return _serializer().dumps({"i": room.institute_id, "r": room.id, "t": room.qr_token})


def verify_qr_payload(payload: str) -> dict | None:
    """
    Decode + verify a scanned QR payload. Returns the original dict
    ({"i": institute_id, "r": room_id, "t": qr_token}) if the signature
    is valid, or None if it's been tampered with / isn't ours at all.
    Still check the returned room_id/qr_token against the database at
    the call site — a valid signature only proves WE issued it, not
    that the room hasn't since been deleted or regenerated.
    """
    try:
        return _serializer().loads(payload)
    except BadSignature:
        return None
