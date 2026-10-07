import os

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Magic numbers checked so a renamed executable is not accepted as a PDF.
_SIGNATURES = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"],
    ".jpeg": [b"\xff\xd8\xff"],
}


def _check_file(f, allowed):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in allowed:
        raise ValidationError(f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(allowed))}.")
    if f.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(f"File too large. Maximum size is {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB.")
    pos = f.tell() if hasattr(f, "tell") else 0
    try:
        f.seek(0)
        head = f.read(8)
    finally:
        f.seek(pos)
    if not any(head.startswith(sig) for sig in _SIGNATURES[ext]):
        raise ValidationError("File content does not match its extension.")


def validate_document_upload(f):
    _check_file(f, ALLOWED_DOCUMENT_EXTENSIONS)


def validate_image_upload(f):
    _check_file(f, ALLOWED_IMAGE_EXTENSIONS)
