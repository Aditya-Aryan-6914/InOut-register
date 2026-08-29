"""
Face verification for check-in — one factor of the QR + face + location
triple-check.

IMPORTANT — READ BEFORE YOU DEMO OR SUBMIT THIS
--------------------------------------------------
This uses OpenCV's built-in LBPH (Local Binary Patterns Histograms)
recognizer, NOT deep-learning face embeddings (the kind `face_recognition`
/ dlib or a cloud face API would give you). The difference matters:

  - dlib/FaceNet-style embeddings: a 128-d vector per face, trained on
    millions of faces, robust to lighting/angle/expression, industry
    standard for a reason.
  - LBPH (this file): a classical, texture-pattern-based algorithm.
    Much more sensitive to lighting, pose, and camera angle. It's a
    real, working face-recognition algorithm — not a placeholder — but
    meaningfully weaker than what a production attendance system would
    want, and easier to fool with a printed photo (no liveness check
    here at all).

Why this file uses it anyway: dlib has to be compiled from source and
that build alone can take 15-30+ minutes and needs system build tools
that a typical dev machine (or this project's deployment target) may
not have. LBPH installs in seconds via `opencv-contrib-python` and is
genuinely good enough to demonstrate the concept for a college project.

If you ever need this to be actually secure (not just architecturally
correct), swap `_compare` below for `face_recognition.face_distance()`
once you're on a machine that can build dlib, or call a cloud face-match
API instead. Everything else in the check-in flow (QR signing, geofence,
AttendanceLog, dashboard) stays the same either way — this file is the
only thing you'd need to replace.
"""
from typing import Optional

import cv2
import cv2.typing
import numpy as np

FACE_SIZE = (200, 200)

# LBPH "distance" is unbounded (lower = more similar). This threshold
# was set empirically: identical images score 0, the same face under
# different lighting/cropping scored ~28 in testing, and a completely
# unrelated image scored ~156. 70 sits comfortably between those with
# margin on both sides, but if you find it too strict/loose for your
# actual camera setup, this is the one number to tune.
MATCH_THRESHOLD = 70.0

_cascade: Optional[cv2.CascadeClassifier] = None


class FaceVerificationError(ValueError):
    """Raised when a face can't be found/compared; message is safe to show the user."""


def _get_cascade() -> cv2.CascadeClassifier:
    global _cascade
    if _cascade is None:
        # cv2's type stubs don't declare the `data` submodule even
        # though it exists and works fine at runtime (confirmed against
        # the installed opencv-contrib-python-headless package).
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"  # type: ignore[reportAttributeAccessIssue]
        _cascade = cv2.CascadeClassifier(cascade_path)
    return _cascade


def _load_gray(source) -> Optional[cv2.typing.MatLike]:
    """source is either a filesystem path (str) or raw image bytes."""
    if isinstance(source, (bytes, bytearray)):
        arr = np.frombuffer(source, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    else:
        img = cv2.imread(source)
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _detect_and_crop_face(gray_image) -> Optional[cv2.typing.MatLike]:
    faces = _get_cascade().detectMultiScale(
        gray_image, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
    )
    if len(faces) == 0:
        return None
    # If more than one face is in frame, use the largest — almost
    # always the person closest to the camera, i.e. the one scanning.
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    crop = gray_image[y:y + h, x:x + w]
    return cv2.resize(crop, FACE_SIZE)


def compare_faces(registered_photo_abs_paths: list[str], captured_image_bytes: bytes) -> tuple[bool, float]:
    """
    Compares a live camera capture against a user's registered face
    samples. Returns (matched, distance) — lower distance means more
    similar. Raises FaceVerificationError (safe to show directly to
    the user) if a face can't be located in the capture, or in *every*
    registered sample, which is a distinct, more actionable failure
    than "didn't match".

    Accepts a LIST of registered photos (not just one) on purpose:
    LBPH trained on a single reference image is very sensitive to
    lighting/pose/expression differences between that one photo and
    whatever the live capture happens to look like. Training on
    several samples of the same person — ideally spanning some natural
    variation — gives LBPH a much more forgiving, realistic model of
    "what this person's face looks like" and directly reduces false
    check-in rejections. Any individual sample that's missing, unreadable,
    or has no detectable face is silently skipped rather than failing
    the whole comparison, since a user is expected to accumulate samples
    over time via "Improve Face" and not all of them need to be perfect.
    """
    registered_faces = []
    for path in registered_photo_abs_paths:
        gray = _load_gray(path)
        if gray is None:
            continue
        face = _detect_and_crop_face(gray)
        if face is None:
            continue
        registered_faces.append(face)

    if not registered_faces:
        raise FaceVerificationError(
            "No usable registered face photo was found for your account. Contact your admin."
        )

    captured_gray = _load_gray(captured_image_bytes)
    if captured_gray is None:
        raise FaceVerificationError("That doesn't look like a valid photo. Please try again.")

    captured_face = _detect_and_crop_face(captured_gray)
    if captured_face is None:
        raise FaceVerificationError("No face detected. Make sure your face is clearly visible and try again.")

    # cv2.face (from opencv-contrib) has notoriously incomplete type
    # stubs — LBPHFaceRecognizer_create isn't declared even though it's
    # a real, working part of the installed package (confirmed at
    # runtime). Same category of issue as the qrcode.save() ignore in
    # admin/routes.py.
    recognizer = cv2.face.LBPHFaceRecognizer_create()  # type: ignore[reportAttributeAccessIssue]
    recognizer.train(registered_faces, np.array([0] * len(registered_faces)))
    _, distance = recognizer.predict(captured_face)

    return distance <= MATCH_THRESHOLD, float(distance)
