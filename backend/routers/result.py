from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from celery.result import AsyncResult
from models.database import get_db
from models.evidence import Evidence, AgentResult
from core.celery_app import celery_app

router = APIRouter(prefix="/api", tags=["result"])


@router.get("/result/{task_id}")
def get_result(task_id: str, db: Session = Depends(get_db)):
    task = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": task_id,
        "state": task.state,
    }

    if task.state == "PENDING":
        response["detail"] = "Task is waiting to be processed"

    elif task.state == "STARTED":
        response["detail"] = "Task is currently running"

    elif task.state == "SUCCESS":
        result = task.result or {}
        evidence_id = result.get("evidence_id")
        agent_results = []

        if evidence_id:
            rows = db.query(AgentResult).filter(AgentResult.evidence_id == evidence_id).all()
            agent_results = [
                {
                    "agent_name": r.agent_name,
                    "confidence_score": r.confidence_score,
                    "findings": r.findings,
                    "heatmap_path": r.heatmap_path,
                }
                for r in rows
            ]

        response.update({
            "evidence_id": evidence_id,
            "verdict": result.get("verdict"),
            "overall_score": result.get("overall_score"),
            "agent_results": agent_results,
        })

    elif task.state == "FAILURE":
        response["detail"] = str(task.info)

    return response


@router.get("/status/{file_id}")
def get_evidence_status(file_id: str, db: Session = Depends(get_db)):
    evidence = db.query(Evidence).filter(Evidence.id == file_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return {
        "file_id": file_id,
        "status": evidence.status,
        "filename": evidence.original_filename,
        "file_type": evidence.file_type,
        "upload_time": evidence.upload_time.isoformat() if evidence.upload_time else None,
    }
