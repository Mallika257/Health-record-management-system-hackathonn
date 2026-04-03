"""
File upload service — local storage with presigned-URL-style pattern.
In production, swap _save_local for S3/GCS.
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import Tuple

from fastapi import HTTPException, UploadFile

from app.core.config import settings


UPLOAD_ROOT = Path(settings.UPLOAD_DIR)
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class FileService:

    @staticmethod
    def _ensure_dir(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate(file: UploadFile) -> None:
        if file.content_type not in settings.ALLOWED_REPORT_TYPES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported media type: {file.content_type}. "
                       f"Allowed: {settings.ALLOWED_REPORT_TYPES}",
            )

    @staticmethod
    async def upload_report(
        file: UploadFile,
        patient_id: str,
    ) -> Tuple[str, str, int, str]:
        """
        Save file to disk.
        Returns: (file_url, file_name, size_bytes, mime_type)
        """
        FileService._validate(file)

        dest_dir = UPLOAD_ROOT / "reports" / patient_id
        FileService._ensure_dir(dest_dir)

        ext       = Path(file.filename).suffix
        safe_name = f"{uuid.uuid4()}{ext}"
        dest_path = dest_dir / safe_name

        # Read and size-check
        content = await file.read()
        if len(content) > MAX_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB} MB",
            )

        with open(dest_path, "wb") as f:
            f.write(content)

        relative_url = f"/uploads/reports/{patient_id}/{safe_name}"
        return relative_url, file.filename, len(content), file.content_type

    @staticmethod
    def delete_file(file_url: str) -> None:
        """Remove file from disk. Silently ignore if not found."""
        rel = file_url.lstrip("/")
        path = UPLOAD_ROOT.parent / rel
        if path.exists():
            path.unlink()
