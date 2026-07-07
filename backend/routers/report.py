from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from models.database import get_db
from models.evidence import Evidence, AgentResult, FinalVerdict, AuditLog

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report/{file_id}")
def get_report(file_id: str, db: Session = Depends(get_db)):
    evidence = db.query(Evidence).filter(Evidence.id == file_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if evidence.status != "done":
        raise HTTPException(status_code=202, detail=f"Analysis not complete yet. Status: {evidence.status}")

    agent_results = db.query(AgentResult).filter(AgentResult.evidence_id == file_id).all()
    verdict = db.query(FinalVerdict).filter(FinalVerdict.evidence_id == file_id).first()
    audit = db.query(AuditLog).filter(AuditLog.evidence_id == file_id).first()

    return {
        "file_id": file_id,
        "filename": evidence.original_filename,
        "file_type": evidence.file_type,
        "file_hash": evidence.file_hash,
        "upload_time": evidence.upload_time.isoformat() if evidence.upload_time else None,
        "verdict": {
            "label": verdict.verdict if verdict else None,
            "overall_score": verdict.overall_score if verdict else None,
            "manipulation_type": verdict.manipulation_type if verdict else None,
            "manipulation_confidence": verdict.manipulation_confidence if verdict else None,
            "gan_attribution": verdict.gan_attribution if verdict else None,
            "gan_confidence": verdict.gan_confidence if verdict else None,
            "reasoning": verdict.reasoning if verdict else [],
            "llm_summary": verdict.llm_summary if verdict else None,
            "timestamp": verdict.timestamp.isoformat() if verdict and verdict.timestamp else None,
        },
        "agent_results": [
            {
                "agent_name": r.agent_name,
                "confidence_score": r.confidence_score,
                "findings": r.findings,
                "heatmap_path": r.heatmap_path,
                "extras": r.extras,   # Phase 6: frame_scores, gradcam_path, feature_importance, ...
            }
            for r in agent_results
        ],
        "audit": {
            "blockchain_hash": audit.blockchain_hash if audit else None,
            "chain_of_custody": audit.chain_of_custody if audit else [],
        },
    }


@router.get("/report/{file_id}/pdf")
def get_report_pdf(file_id: str, db: Session = Depends(get_db)):
    """Phase 6: Legal Evidence Package — court-style PDF with XAI exhibits."""
    evidence = db.query(Evidence).filter(Evidence.id == file_id).first()
    if not evidence:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if evidence.status != "done":
        raise HTTPException(status_code=202, detail=f"Analysis not complete yet. Status: {evidence.status}")

    agent_results = db.query(AgentResult).filter(AgentResult.evidence_id == file_id).all()
    verdict = db.query(FinalVerdict).filter(FinalVerdict.evidence_id == file_id).first()
    audit = db.query(AuditLog).filter(AuditLog.evidence_id == file_id).first()

    from core.pdf_report import build_pdf
    try:
        pdf_path = build_pdf(evidence, verdict, agent_results, audit)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=f"TrustSphere_Evidence_{file_id}.pdf",
    )
