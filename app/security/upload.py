"""File upload validation for MAA input files.

Enforces:
  - Max file size per file
  - Max total upload size
  - Max file count
  - Allowed MIME types
  - URL-based extension check
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Default limits (can be overridden by settings)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB per file
MAX_TOTAL_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB total
MAX_FILE_COUNT = 20

ALLOWED_MIME_PREFIXES = {
    "image/": [".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"],
    "video/": [".mp4", ".mov", ".avi", ".webm", ".mkv"],
    "audio/": [".mp3", ".wav", ".aac", ".ogg", ".m4a"],
    "application/pdf": [".pdf"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": [".docx"],
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"],
    "text/plain": [".txt", ".csv"],
}

EXT_TO_MIME = {}
for mime, exts in ALLOWED_MIME_PREFIXES.items():
    for ext in exts:
        EXT_TO_MIME[ext] = mime


class FileUploadError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def validate_input_files(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate a list of input files.

    Args:
        files: List of file dicts with keys: url, name, type, size.

    Returns:
        The validated (and possibly cleaned) list of files.

    Raises:
        FileUploadError: If any file fails validation.
    """
    if not isinstance(files, list):
        raise FileUploadError("files must be a list")

    if len(files) > MAX_FILE_COUNT:
        raise FileUploadError(
            f"Too many files: {len(files)} > {MAX_FILE_COUNT}"
        )

    total_size = 0
    validated = []

    for i, f in enumerate(files):
        if not isinstance(f, dict):
            raise FileUploadError(f"File {i} is not a dict")

        url = (f.get("url") or "").strip()
        name = f.get("name", "")
        mime_type = f.get("type", "")
        size = f.get("size", 0)

        if not url:
            raise FileUploadError(f"File {i} ({name!r}) has no url")

        # Check extension
        ext = _get_extension(url, name)
        if not ext:
            raise FileUploadError(
                f"File {i} ({name!r}) has no recognizable extension"
            )

        # Check MIME type if provided
        if mime_type:
            expected_mime = EXT_TO_MIME.get(ext)
            if expected_mime and not mime_type.startswith(expected_mime.split("/")[0]):
                logger.warning(
                    "MIME type mismatch",
                    extra={"file": name, "declared": mime_type, "expected": expected_mime},
                )

        # Check size
        if size is not None:
            try:
                size_int = int(size)
            except (TypeError, ValueError):
                size_int = 0
            if size_int > MAX_FILE_SIZE_BYTES:
                raise FileUploadError(
                    f"File {i} ({name!r}) exceeds max size: {size_int} > {MAX_FILE_SIZE_BYTES}"
                )
            total_size += size_int

        validated.append({
            "url": url,
            "name": name,
            "type": mime_type,
            "size": size,
        })

    if total_size > MAX_TOTAL_SIZE_BYTES:
        raise FileUploadError(
            f"Total upload size exceeds limit: {total_size} > {MAX_TOTAL_SIZE_BYTES}"
        )

    return validated


def _get_extension(url: str, name: str) -> str:
    """Extract file extension from URL or filename."""
    for candidate in [url, name]:
        if "." in candidate:
            ext = "." + candidate.rsplit(".", 1)[-1].lower()
            if ext in EXT_TO_MIME:
                return ext
    return ""
