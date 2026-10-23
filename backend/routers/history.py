from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from models.database import get_db
from models.evidence import Evidence, FinalVerdict

router = APIRouter(prefix="/api", tags=["history"])


@router.get("/evidence")
def list_evidence(limit: int = 100, db: Session = Depends(get_db)):
    """Most recent analyses first, with their verdict (used by the web app's History page)."""
    rows = (
        db.query(Evidence, FinalVerdict)
        .outerjoin(FinalVerdict, FinalVerdict.evidence_id == Evidence.id)
        .order_by(Evidence.upload_time.desc())
        .limit(max(1, min(limit, 500)))
        .all()
    )
    return [
        {
            "file_id": e.id,
            "filename": e.original_filename,
            "file_type": e.file_type,
            "file_hash": e.file_hash,
            "status": e.status,
            "upload_time": e.upload_time.isoformat() if e.upload_time else None,
            "verdict": v.verdict if v else None,
            "overall_score": v.overall_score if v else None,
            "manipulation_type": v.manipulation_type if v else None,
        }
        for e, v in rows
    ]
