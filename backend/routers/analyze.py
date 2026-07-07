from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from models.database import get_db
from models.evidence import Evidence
from core.tasks import analyze_evidence

router = APIRouter(prefix="/api", tags=["analyze"])


@router.post("/analyze/{file_id}")
def trigger_analysis(file_id: str, db: Session = Depends(get_db)):
    evidence = db.query(Evidence).filter(Evidence.id == file_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if evidence.status == "analyzing":
        raise HTTPException(status_code=409, detail="Analysis already in progress")

    evidence.status = "pending"
    db.commit()

    task = analyze_evidence.delay(evidence.id)
    return {"file_id": file_id, "task_id": task.id, "status": "queued"}
