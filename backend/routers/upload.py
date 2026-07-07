import os
import hashlib
import mimetypes
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.evidence import Evidence
from core.tasks import analyze_evidence

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", 104857600))  # 100 MB

ALLOWED_TYPES = {
    "image": ["image/jpeg", "image/png", "image/webp", "image/gif", "image/bmp"],
    "video": ["video/mp4", "video/avi", "video/mov", "video/mkv", "video/webm"],
    "audio": ["audio/mpeg", "audio/wav", "audio/ogg", "audio/flac", "audio/mp4"],
    "document": ["application/pdf", "application/msword",
                  "application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
}


def _detect_file_type(mime: str) -> str:
    for file_type, mimes in ALLOWED_TYPES.items():
        if mime in mimes:
            return file_type
    return ""


@router.post("/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 100 MB)")

    mime = file.content_type or mimetypes.guess_type(file.filename or "")[0] or ""
    file_type = _detect_file_type(mime)
    if not file_type:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {mime}")

    file_hash = hashlib.sha256(content).hexdigest()

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    suffix = Path(file.filename or "file").suffix
    dest = UPLOAD_DIR / f"{file_hash}{suffix}"
    dest.write_bytes(content)

    evidence = Evidence(
        original_filename=file.filename or "unknown",
        file_type=file_type,
        file_path=str(dest),
        file_hash=file_hash,
        status="pending",
    )
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    task = analyze_evidence.delay(evidence.id)

    return {
        "file_id": evidence.id,
        "task_id": task.id,
        "filename": evidence.original_filename,
        "file_type": file_type,
        "file_hash": file_hash,
        "status": "pending",
    }
